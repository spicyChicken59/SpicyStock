// Browser interactions for the research cockpit. Everything is served from this
// checkout, including explicitly labelled fixtures; no market service is called.
// node tools/research_cockpit_smoke.mjs [--shots /tmp/research-shots]
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = join(repo, 'docs');
const [recorded, fixture, history, ledger] = await Promise.all([
  'docs/data.json', 'tests/fixtures/data.json', 'tests/fixtures/history/data.json',
  'tests/fixtures/history/ledger.json'
].map(async path => JSON.parse(await readFile(join(repo, path), 'utf8'))));
assert.equal(fixture.run.fixture, true);
assert.equal(history.run.fixture, true);
const args = process.argv.slice(2);
const shotIndex = args.indexOf('--shots');
const shots = shotIndex < 0 ? null : resolve(args[shotIndex + 1]);
if (shots) await mkdir(shots, { recursive: true });
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    const path = decodeURIComponent(new URL(request.url, 'http://research.local').pathname);
    const file = resolve(docs, '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(docs + sep)) { response.writeHead(403).end(); return; }
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end(); }
});
async function chromiumTool() {
  for (const root of ['', ...(process.env.NODE_PATH || '').split(':').filter(Boolean)]) {
    try {
      const module = await import(root ? pathToFileURL(join(root, 'playwright/index.js')).href : 'playwright');
      if (module.chromium || module.default?.chromium) return module.chromium || module.default.chromium;
    } catch { /* Try another installed runtime location. */ }
  }
  throw new Error('Playwright Chromium is required; research interactions cannot be skipped.');
}
let browser;
const errors = [];
let checks = 0;
function pass(name) { checks++; console.log('PASS ' + name); }
// A fresh page must request fresh application assets even if a returning
// browser still holds an older response for each unversioned URL.
const pageAssets = [
  'stock.css', 'stock-home.css', 'signal-map.js',
  'stock-cockpit.css', 'stock-cockpit.js', 'stock-desk.css', 'stock-desk.js',
  'stock-replay.css', 'stock-replay.js',
  'stockbee-workbench.css', 'stockbee-workbench.js', 'stockbee-plan.css', 'stockbee-plan.js'
];
const indexHTML = await readFile(join(docs, 'index.html'), 'utf8');
const assetBase = 'https://research.local/';
const linkedAssets = [...indexHTML.matchAll(/<(?:link|script)\b[^>]*\b(?:href|src)=["']([^"']+)["'][^>]*>/gi)]
  .map(match => new URL(match[1], assetBase));
await Promise.all(pageAssets.map(async asset => {
  const matches = linkedAssets.filter(url => url.origin === new URL(assetBase).origin && url.pathname === '/' + asset);
  assert.equal(matches.length, 1, asset + ' must be loaded once from this site.');
  const digest = createHash('sha256').update(await readFile(join(docs, asset))).digest('hex').slice(0, 12);
  assert.deepEqual(matches[0].searchParams.getAll('v'), [digest],
    asset + ' needs a v= content hash matching its exact file bytes so returning browsers receive this release.');
}));
pass('every page-owned CSS and JavaScript URL carries its current content hash');
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
try {
  browser = await (await chromiumTool()).launch();
  async function open(data = fixture, initScript) {
    const context = await browser.newContext({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
    if (initScript) await context.addInitScript(initScript);
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    const state = { data, ledger, archiveRequests: 0, archiveStatus: 200, archiveGate: null };
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) { await route.fulfill({ status: 200, body: '' }); return; }
      if (url.pathname === '/data.json') {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(state.data) }); return;
      }
      if (url.pathname === '/ledger.json') {
        state.archiveRequests++;
        const body = JSON.stringify(state.ledger), status = state.archiveStatus;
        if (state.archiveGate) await state.archiveGate;
        await route.fulfill({ status, contentType: 'application/json', body }); return;
      }
      await route.continue();
    });
    await page.goto(origin, { waitUntil: 'load' });
    await page.locator('#session-cockpit').waitFor({ state: 'visible' });
    await page.locator('#signal-search').waitFor({ state: 'visible' });
    return { context, page, state };
  }
  async function screenshot(page, selector, name) {
    if (!shots) return;
    await page.locator(selector).scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(shots, name + '.png') });
  }
  async function visibleTickers(page) {
    return page.locator('.signal-card:visible .signal-card-select').allTextContents();
  }

  const live = await open(recorded);
  assert.equal(await live.page.locator('#funnel-card').isVisible(), true, 'The full report must be available by default.');
  assert.equal(live.state.archiveRequests, 0, 'Opening the cockpit must not eagerly download the archive.');
  if (!recorded.candidates.length) {
    assert.equal(await live.page.locator('.signal-card').count(), 0);
    assert.equal(await live.page.locator('.signal-point').count(), 0);
    assert.match(await live.page.locator('#session-cockpit').textContent(), /no scored|nothing scored|0 scored|no candidates|quiet/i);
    assert.match(await live.page.locator('.signal-map-empty').textContent(), /No scored signals/);
  }
  await screenshot(live.page, '#session-cockpit', 'cockpit-recorded-phone');
  pass('recorded cockpit is truthful about an empty session and loads without the archive');
  // An empty ranking can mean the gate refused every burst. That is different
  // from a quiet market; seed this known state without fabricating a live run.
  const refused = structuredClone(recorded);
  refused.run.bursts = 7;
  refused.run.status = 'ok';
  refused.candidates = [];
  refused.run.scored = 0;
  refused.runs = [{ ...refused.run }];
  await live.page.evaluate(d => { window.SCStockCockpit.render(d); window.SCStockReplay.render(d); }, refused);
  assert.doesNotMatch(await live.page.locator('#cockpit-title').textContent(), /quiet/i);
  assert.doesNotMatch(await live.page.locator('.stock-replay__session-title').textContent(), /quiet/i);
  assert.match(await live.page.locator('#stock-replay-details').textContent(), /No scored candidates/);
  pass('bursts refused before scoring are not presented as a quiet market');
  await live.context.close();

  const app = await open();
  const { page, state } = app;
  assert.equal(await page.locator('#fixture-banner').isVisible(), true);
  assert.deepEqual(await visibleTickers(page), fixture.candidates.map(c => c.ticker));
  const originalAxes = await page.locator('.signal-axis').allTextContents();
  const selected = fixture.candidates[4];
  await page.locator('#signal-search').fill(selected.ticker.toLowerCase());
  assert.deepEqual(await visibleTickers(page), [selected.ticker]);
  assert.equal(await page.locator('.signal-point').count(), 1);
  assert.equal(await page.locator('.signal-point').getAttribute('data-signal-index'), '4');
  assert.match(await page.locator('.signal-card:visible .signal-rank').textContent(), new RegExp('\\b' + selected.rank + '\\b'));
  assert.deepEqual(await page.locator('.signal-axis').allTextContents(), originalAxes, 'Filtering must not silently change the coordinate scale.');
  assert.equal(await page.locator('.signal-point-label').evaluate(label => {
    const text = document.createRange();
    text.selectNodeContents(label);
    return text.getClientRects().length;
  }), 1, 'A normal ticker label must remain on one readable line.');
  await screenshot(page, '#signal-workspace', 'signal-filtered-phone');
  await page.locator('#signal-search').fill('no-such-recorded-ticker');
  assert.equal(await page.locator('.signal-card:visible').count(), 0);
  assert.equal(await page.locator('.signal-point').count(), 0);
  assert.equal(await page.locator('.signal-no-matches').isVisible(), true);
  await page.locator('.signal-clear').click();
  assert.deepEqual(await visibleTickers(page), fixture.candidates.map(c => c.ticker));
  assert.equal(await page.locator('#signal-search').inputValue(), '');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'signal-search');
  pass('ticker search keeps recorded rank and map scale; no-match and keyboard-friendly reset work');

  for (const [filter, expected] of [
    ['shortlist', fixture.candidates.filter(c => Number.isFinite(c.rank) && c.rank > 0 && c.rank <= fixture.run.shortlist_size)],
    ['claude', fixture.candidates.filter(c => c.provenance?.source === 'claude')],
    ['fallback', fixture.candidates.filter(c => c.provenance?.source === 'fallback')],
    ['volume', fixture.candidates.filter(c => Number.isFinite(c.volume_ratio) && c.volume_ratio >= 3)]
  ]) {
    await page.locator(`[data-signal-filter="${filter}"]`).click();
    assert.deepEqual(await visibleTickers(page), expected.map(c => c.ticker), filter);
    assert.equal(await page.locator(`[data-signal-filter="${filter}"]`).getAttribute('aria-pressed'), 'true');
  }
  await page.locator('.signal-clear').click();
  await page.locator('#signal-sort').selectOption('gain');
  assert.deepEqual(await visibleTickers(page), [...fixture.candidates].sort((a, b) => b.gain_pct - a.gain_pct).map(c => c.ticker));
  await page.locator('#signal-sort').selectOption('volume');
  assert.deepEqual(await visibleTickers(page), [...fixture.candidates].sort((a, b) => b.volume_ratio - a.volume_ratio).map(c => c.ticker));
  await page.locator('.signal-clear').click();
  assert.equal(await page.locator('#signal-sort').inputValue(), 'rank');
  assert.deepEqual(await visibleTickers(page), fixture.candidates.map(c => c.ticker));
  pass('shortlist, provenance and volume filters plus both numeric sorts preserve the recorded candidates');

  // Seed only a deliberately incomplete record; use the public controls for
  // the behavior under test. Missing coordinates must never become zero dots.
  const incomplete = structuredClone(fixture);
  incomplete.candidates[0].gain_pct = null;
  incomplete.candidates[1].volume_ratio = null;
  delete incomplete.candidates[2].provenance;
  await page.evaluate(d => window.SCStockSignals.render(d), incomplete);
  await page.locator('#signal-search').fill(incomplete.candidates[0].ticker);
  assert.equal(await page.locator('.signal-card:visible').count(), 1);
  assert.equal(await page.locator('.signal-point').count(), 0);
  assert.match(await page.locator('.signal-card:visible').textContent(), /Not recorded/);
  await page.locator('.signal-clear').click();
  await page.locator('[data-signal-filter="claude"]').click();
  assert.equal((await visibleTickers(page)).includes(incomplete.candidates[2].ticker), false);
  await page.locator('[data-signal-filter="fallback"]').click();
  assert.equal((await visibleTickers(page)).includes(incomplete.candidates[2].ticker), false);
  pass('missing measurements remain listed without invented map points or score provenance');
  await page.reload({ waitUntil: 'load' });
  await page.locator('#signal-search').waitFor({ state: 'visible' });

  const choices = fixture.candidates.slice(0, 4).map(c => c.ticker);
  for (const ticker of choices) await page.locator(`[data-stock-compare="${ticker}"]`).click();
  assert.equal(await page.locator('[data-desk-ticker]').count(), 3);
  assert.match(await page.locator('#desk-compare-count').textContent(), /3 \/ 3/);
  assert.match(await page.locator('#desk-message').textContent(), /Three candidates are already selected/);
  assert.equal(await page.locator('#desk-comparison-tray').isVisible(), true);
  assert.match(await page.locator('#desk-tray-notice').textContent(), /Three selected/);
  assert.match(await page.locator('#desk-tray-summary').textContent(), /3 \/ 3/);
  await page.locator('#desk-tray-open').click();
  assert.equal(await page.locator('#desk-panel-compare').isVisible(), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), 'desk-panel-compare');
  assert.equal(await page.locator(`[data-stock-compare="${choices[3]}"]`).getAttribute('aria-pressed'), 'false');
  for (const candidate of fixture.candidates.slice(0, 3)) {
    const card = page.locator(`[data-desk-ticker="${candidate.ticker}"]`);
    assert.match(await card.textContent(), new RegExp(candidate.score.toFixed(1).replace('.', '\\.')));
    assert.ok((await card.textContent()).includes(candidate.key_risk), 'Comparison retains the recorded risk.');
  }
  await page.locator(`[data-desk-ticker="${choices[0]}"]`).getByRole('button', { name: `Remove ${choices[0]} from comparison`, exact: true }).click();
  await page.locator(`[data-stock-compare="${choices[3]}"]`).click();
  assert.deepEqual(await page.locator('[data-desk-ticker]').evaluateAll(nodes => nodes.map(n => n.dataset.deskTicker)), choices.slice(1));
  await screenshot(page, '#stock-desk', 'compare-phone');
  pass('comparison keeps the recorded facts, limits selection to three and supports replacement');

  const savedTicker = choices[0];
  const note = 'Revisit volume after the next scan. <img src=x onerror=alert(1)> & keep the recorded risk in view.';
  await page.locator(`[data-stock-save="${savedTicker}"]`).click();
  await page.locator('#desk-tab-saved').click();
  await page.locator(`#desk-note-${savedTicker}`).fill(note);
  assert.equal(await page.locator('#desk-comparison-tray').isVisible(), false, 'Editing notes must clear the floating tray from the keyboard area.');
  assert.equal(await page.evaluate(() => document.body.classList.contains('desk-has-tray')), false);
  assert.match(await page.locator(`#desk-note-count-${savedTicker}`).textContent(), /unsaved edits/);
  await page.locator('#desk-tab-compare').click();
  await page.locator('#desk-tab-saved').click();
  assert.equal(await page.locator(`#desk-note-${savedTicker}`).inputValue(), note, 'Tab changes must retain an unsaved note.');
  await page.getByRole('button', { name: `Save note for ${savedTicker}`, exact: true }).click();
  assert.match(await page.locator('#desk-message').textContent(), /note saved in this browser/);
  await page.locator('#desk-tab-compare').click();
  assert.equal(await page.locator('#desk-comparison-tray').isVisible(), true);
  await page.locator('#desk-tray-clear').click();
  assert.equal(await page.locator('[data-desk-ticker]').count(), 0);
  assert.equal(await page.locator('#desk-comparison-tray').isVisible(), false);
  assert.equal(await page.locator('[data-stock-compare][aria-pressed="true"]').count(), 0);
  assert.equal(await page.evaluate(() => document.body.classList.contains('desk-has-tray')), false);
  pass('comparison tray opens the desk, stays out of note editing and clears selection without leaving page padding');
  await page.reload({ waitUntil: 'load' });
  await page.locator('#desk-tab-saved').click();
  assert.equal(await page.locator(`#desk-note-${savedTicker}`).inputValue(), note);
  assert.equal(await page.locator('#stock-desk img').count(), 0, 'Notes must stay plain text.');
  await page.locator('#desk-add-ticker').fill('researchzz');
  await page.getByRole('button', { name: 'Add ticker', exact: true }).click();
  assert.match(await page.locator('[data-desk-saved="RESEARCHZZ"]').textContent(), /Not a candidate in this snapshot/);
  assert.equal(await page.locator('[data-desk-saved="RESEARCHZZ"] .desk-saved-metrics').count(), 0);
  await screenshot(page, '#stock-desk', 'saved-notes-phone');
  state.data = recorded;
  await page.reload({ waitUntil: 'load' });
  await page.locator('#desk-tab-saved').click();
  assert.equal(await page.locator(`#desk-note-${savedTicker}`).inputValue(), note);
  if (!recorded.candidates.some(c => c.ticker === savedTicker)) {
    assert.match(await page.locator(`[data-desk-saved="${savedTicker}"]`).textContent(), /Not a candidate in this snapshot/);
    assert.equal(await page.locator(`[data-desk-saved="${savedTicker}"] .desk-saved-metrics`).count(), 0);
  }
  pass('saved notes survive reload and session changes without carrying old metrics into the new snapshot');
  state.data = fixture;
  await page.reload({ waitUntil: 'load' });

  await page.locator('#cockpit-focus').focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#cockpit-focus').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('#funnel-card').isVisible(), false);
  for (const selector of ['#signal-workspace', '#stock-desk', '#stock-replay']) {
    assert.equal(await page.locator(selector).isVisible(), true, selector + ' remains available in focus view');
  }
  await page.locator('.cockpit-stage').first().click();
  assert.equal(await page.locator('#cockpit-focus').getAttribute('aria-pressed'), 'false');
  assert.equal(await page.locator('#funnel-card').isVisible(), true);
  pass('keyboard focus mode keeps the research workspace and report links restore the full report');

  for (const ticker of choices.slice(0, 3)) await page.locator(`[data-stock-compare="${ticker}"]`).click();

  // Check actual control geometry, not just body overflow:
  // a clipping rule on the page must not disguise a broken phone card.
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      await page.locator(`.sc-theme-toggle [data-theme="${theme}"]`).click();
      const issues = await page.evaluate(() => {
        const problems = [], tolerance = 2;
        const sections = ['#session-cockpit', '#signal-workspace', '#stock-desk', '#stock-replay'].map(id => document.querySelector(id));
        if (document.documentElement.scrollWidth > innerWidth + 1) problems.push('page is wider than viewport');
        const navigation = document.querySelector('#page-index');
        navigation.scrollLeft = 0;
        const navigationBox = navigation.getBoundingClientRect();
        const firstLink = navigation.querySelector('a').getBoundingClientRect();
        if (firstLink.left < navigationBox.left || firstLink.right > navigationBox.right) problems.push('workspace navigation hides its first link');
        for (const section of sections) {
          const outer = section.getBoundingClientRect();
          if (outer.left < -tolerance || outer.right > innerWidth + tolerance) problems.push(section.id + ' outside viewport');
          for (const node of section.querySelectorAll('button,input,select,textarea')) {
            if (!node.getClientRects().length || node.closest('[hidden]')) continue;
            // The session rail deliberately scrolls inside its own container.
            if (node.closest('.stock-replay__rail')) continue;
            const box = node.getBoundingClientRect(), style = getComputedStyle(node);
            const tray = node.closest('#desk-comparison-tray');
            const boundary = tray ? tray.getBoundingClientRect() : outer;
            if (box.width < 1 || box.height < 1) continue;
            if (box.left < boundary.left - tolerance || box.right > boundary.right + tolerance) problems.push((node.id || node.className) + ' outside its section');
            if (!node.matches('.signal-point') && box.height < 43.5) problems.push((node.id || node.className) + ' touch target below 44px');
            if (!node.matches('.signal-point') && parseFloat(style.fontSize) < 12) problems.push((node.id || node.className) + ' unreadably small text');
          }
        }
        const tray = document.querySelector('#desk-comparison-tray');
        if (tray && !tray.hidden) {
          const box = tray.getBoundingClientRect();
          if (box.left < 0 || box.right > innerWidth || box.top < 0 || box.bottom > innerHeight) problems.push('comparison tray outside viewport');
          if (parseFloat(getComputedStyle(document.body).paddingBottom) < box.height) problems.push('comparison tray has no reserved page space');
        }
        return problems;
      });
      assert.deepEqual(issues, [], `${width}px ${theme}`);
    }
  }
  await page.locator('#signal-search').focus();
  assert.equal(await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement);
    return document.activeElement.id === 'signal-search' && parseFloat(style.outlineWidth) >= 2 && style.outlineStyle !== 'none';
  }), true, 'Keyboard focus must remain visible.');
  assert.equal(await page.evaluate(() => {
    const areas = '#session-cockpit *, #signal-workspace *, #stock-desk *, #stock-replay *';
    return [...document.querySelectorAll(areas)].every(node => getComputedStyle(node).animationName === 'none' || parseFloat(getComputedStyle(node).animationDuration) <= 0.001);
  }), true, 'Reduced-motion preference must avoid ambient research animations.');
  pass('all five research features fit 320px, 390px and desktop in both themes with readable touch and keyboard controls');
  await app.context.close();

  for (const mode of ['blocked', 'corrupt', 'quota']) {
    const init = mode === 'corrupt' ? () => {
      localStorage.setItem('spicystock.research.v1', '{"version":1,"saved":"broken notebook"}');
    } : mode === 'blocked' ? () => {
      const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
      Storage.prototype.getItem = function (key) { if (key === 'spicystock.research.v1') throw new DOMException('Blocked', 'SecurityError'); return get.call(this, key); };
      Storage.prototype.setItem = function (key, value) { if (key === 'spicystock.research.v1') throw new DOMException('Blocked', 'SecurityError'); return set.call(this, key, value); };
    } : () => {
      const set = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, value) { if (key === 'spicystock.research.v1') throw new DOMException('Full', 'QuotaExceededError'); return set.call(this, key, value); };
    };
    const isolated = await open(fixture, init);
    await isolated.page.locator(`[data-stock-save="${savedTicker}"]`).click();
    await isolated.page.locator('#desk-tab-saved').click();
    await isolated.page.locator(`#desk-note-${savedTicker}`).fill('Keep a separate copy.');
    await isolated.page.getByRole('button', { name: `Save note for ${savedTicker}`, exact: true }).click();
    assert.match(await isolated.page.locator('#desk-storage-status').textContent(), /^Only this visit:/);
    assert.match(await isolated.page.locator('#desk-message').textContent(), /only for this visit/);
    assert.equal(await isolated.page.locator(`#desk-note-${savedTicker}`).inputValue(), 'Keep a separate copy.');
    assert.equal(await isolated.page.locator('#signal-search').isEnabled(), true);
    await isolated.context.close();
    pass(mode + ' browser storage keeps research usable and never claims persistence');
  }

  const archive = await open(history);
  const replay = archive.page;
  const latestKey = history.run.date + '|' + history.run.type;
  assert.equal(await replay.locator('#stock-replay-date option').count(), history.runs.length);
  assert.equal(await replay.locator('#stock-replay-date').inputValue(), latestKey);
  assert.equal(archive.state.archiveRequests, 0);
  await replay.locator('#stock-replay-previous').click();
  assert.notEqual(await replay.locator('#stock-replay-date').inputValue(), latestKey);
  await replay.locator('#stock-replay-next').click();
  assert.equal(await replay.locator('#stock-replay-date').inputValue(), latestKey);
  const earlier = ledger.runs.find(run => run.candidates.some(c => c.forward_returns?.d1 != null && c.forward_returns?.from_open?.d1 != null));
  assert.ok(earlier, 'History fixture must exercise both measured return bases.');
  const earlierKey = earlier.date + '|' + earlier.type;
  await replay.locator('#stock-replay-date').selectOption(earlierKey);
  assert.equal(archive.state.archiveRequests, 0, 'Selecting a session should still be summary-only.');
  archive.state.archiveStatus = 503;
  await replay.locator('#stock-replay-load').click();
  await replay.getByRole('button', { name: 'Retry session record', exact: true }).waitFor();
  assert.match(await replay.locator('#stock-replay-details').textContent(), /could not be loaded/i);
  archive.state.archiveStatus = 200;
  archive.state.ledger = { schema_version: 99, app: 'SpicyStock', generated: history.generated, runs: [] };
  await replay.locator('#stock-replay-load').click();
  await replay.getByRole('button', { name: 'Retry session record', exact: true }).waitFor();
  assert.match(await replay.locator('#stock-replay-details').textContent(), /unsupported format/i);
  archive.state.ledger = structuredClone(ledger);
  archive.state.ledger.runs.find(run => run.date === earlier.date && run.type === earlier.type).scored += 1;
  await replay.locator('#stock-replay-load').click();
  await replay.getByRole('button', { name: 'Retry session record', exact: true }).waitFor();
  assert.match(await replay.locator('#stock-replay-details').textContent(), /different session counts/i);
  // The pipeline serializes these files separately; a different generation
  // instant alone is legitimate when the selected session's facts agree.
  archive.state.ledger = { ...ledger, generated: new Date(Date.parse(history.generated) + 1000).toISOString() };
  await replay.locator('#stock-replay-load').click();
  await replay.locator('.stock-replay__candidate').first().waitFor();
  const ordered = [...earlier.candidates].sort((a, b) => a.rank - b.rank).slice(0, 5);
  assert.deepEqual(await replay.locator('.stock-replay__candidate h4').allTextContents(), ordered.map(c => c.ticker));
  assert.match(await replay.locator('#stock-replay-details').textContent(), /synthetic fixture data/);
  assert.match(await replay.locator('#stock-replay-details').textContent(), /latest saved observations/);
  const value = number => typeof number === 'number' && Number.isFinite(number) ? (number > 0 ? '+' : '') + number.toFixed(1) + '%' : 'Not recorded';
  assert.deepEqual(await replay.locator('.stock-replay__candidate').first().locator('.stock-replay__returns dd').allTextContents(),
    [1, 3, 5].map(h => value(ordered[0].forward_returns?.['d' + h])));
  const runRowsBefore = await replay.locator('#runs-table tbody tr').count();
  assert.equal(runRowsBefore, history.runs.length, 'The full report includes every fixture session.');
  const lensCandidate = history.candidates.find(c => c.provenance?.source === 'claude');
  assert.ok(lensCandidate);
  await replay.locator('#signal-search').fill(lensCandidate.ticker.toLowerCase());
  await replay.locator('[data-signal-filter="claude"]').click();
  await replay.locator('#signal-sort').selectOption('volume');
  await replay.evaluate(() => {
    window.__researchDeskRenderBeforeFailure = window.SCStockDesk.render;
    window.SCStockDesk.render = () => { throw new Error('Deliberate research-desk rendering failure'); };
  });
  await replay.locator('#basis-tabs [data-basis="open"]').click();
  assert.equal(await replay.locator('#signal-search').inputValue(), lensCandidate.ticker.toLowerCase());
  assert.equal(await replay.locator('[data-signal-filter="claude"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await replay.locator('#signal-sort').inputValue(), 'volume');
  assert.deepEqual(await visibleTickers(replay), [lensCandidate.ticker]);
  assert.equal(await replay.locator('#stock-desk .workspace-fallback').isVisible(), true);
  assert.equal(await replay.locator('.workspace-fallback').count(), 1, 'A desk failure must stay local to the desk.');
  assert.equal(await replay.locator('#runs-table tbody tr').count(), runRowsBefore);
  assert.equal(await replay.locator('#runs-table').isVisible(), true);
  const reportAfterBasisChange = await replay.locator('#runs-table').textContent();
  await replay.evaluate(() => {
    window.SCStockDesk.render = window.__researchDeskRenderBeforeFailure;
    delete window.__researchDeskRenderBeforeFailure;
  });
  await replay.locator('#stock-desk').getByRole('button', { name: 'Try again', exact: true }).click();
  assert.equal(await replay.locator('#stock-desk .workspace-fallback').count(), 0);
  assert.equal(await replay.locator('#desk-tab-compare').isVisible(), true);
  assert.equal(await replay.locator('#runs-table').textContent(), reportAfterBasisChange, 'Retrying a workspace must not alter the recorded report.');
  pass('an optional workspace failure leaves the full report available and its retry restores only that workspace');
  assert.equal(await replay.locator('#stock-replay-date').inputValue(), earlierKey);
  assert.match(await replay.locator('.stock-replay__returns-label').first().textContent(), /next session’s open/);
  assert.deepEqual(await replay.locator('.stock-replay__candidate').first().locator('.stock-replay__returns dd').allTextContents(),
    [1, 3, 5].map(h => value(ordered[0].forward_returns?.from_open?.['d' + h])));
  await screenshot(replay, '#stock-replay-details', 'replay-open-basis-phone');
  pass('replay navigation, lazy loading, failed and incompatible archive retries preserve dated records and the global return basis');

  assert.notEqual(recorded.run.date, history.run.date, 'Recorded and synthetic sessions must differ for the lens-reset check.');
  archive.state.data = recorded;
  await replay.locator('#snapshot-refresh').click();
  await replay.waitForFunction(date => document.querySelector('.cockpit-session').textContent.includes(date), recorded.run.date);
  assert.equal(await replay.locator('#signal-search').inputValue(), '');
  assert.equal(await replay.locator('[data-signal-filter="all"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await replay.locator('#signal-sort').inputValue(), 'rank');
  pass('lens choices survive return-basis changes and reset when a different published session arrives');
  archive.state.data = history;

  await replay.reload({ waitUntil: 'load' });
  await replay.locator('#stock-replay-date').selectOption(earlierKey);
  let releaseArchive;
  archive.state.archiveGate = new Promise(resolve => { releaseArchive = resolve; });
  const beforeRace = archive.state.archiveRequests;
  const requestStarted = replay.waitForRequest(request => new URL(request.url()).pathname === '/ledger.json');
  await replay.locator('#stock-replay-load').click();
  await requestStarted;
  await replay.locator('#stock-replay-date').selectOption(latestKey);
  assert.equal(await replay.locator('.stock-replay__candidate').count(), 0);
  releaseArchive();
  await replay.getByRole('button', { name: 'Read session candidates', exact: true }).waitFor();
  assert.equal(await replay.locator('.stock-replay__candidate').count(), 0, 'An older request must not paint the previous session over the new selection.');
  assert.equal(await replay.locator('#stock-replay-date').inputValue(), latestKey);
  await replay.locator('#stock-replay-load').click();
  await replay.locator('.stock-replay__candidate').first().waitFor();
  assert.deepEqual(await replay.locator('.stock-replay__candidate h4').allTextContents(), ledger.runs.find(r => r.date === history.run.date && r.type === history.run.type).candidates.slice(0, 5).map(c => c.ticker));
  assert.equal(archive.state.archiveRequests, beforeRace + 1, 'A coherent already-loaded archive should be reused.');
  await archive.context.close();
  pass('changing sessions during an archive request cannot display stale candidates or duplicate the download');

  // These explicitly synthetic strategy records exercise the complete scan
  // queue independently of the fixture's stricter AI-scored candidates.
  const legacyData = structuredClone(fixture);
  delete legacyData.run.stockbee;
  const legacyBee = await open(legacyData);
  await legacyBee.page.locator('#stockbee-workspace').waitFor({ state: 'visible' });
  assert.equal(await legacyBee.page.locator('[data-stockbee-select]').count(), 0);
  assert.equal(await legacyBee.page.locator('.signal-card').count(), fixture.candidates.length);
  assert.match(await legacyBee.page.locator('#h1').textContent(), /on the shortlist$/);
  assert.match(await legacyBee.page.locator('#stockbee-search-results').textContent(), /not yet recorded/);
  assert.match(await legacyBee.page.locator('.sb-pulse').textContent(), /Missing history is not zero activity/);
  assert.equal(await legacyBee.page.locator('.sb-pulse-day').count(), 0);
  assert.equal(await legacyBee.page.locator('.sb-chart svg').count(), 0);
  await legacyBee.context.close();
  pass('legacy snapshots retain their scored candidates without inventing a Stockbee scan queue or breadth');

  const beeData = structuredClone(fixture);
  const beeRow = {
    ticker: 'TESTBEE', date: fixture.run.date, close: 20, high: 20.5, low: 18,
    prev_close: 19, gain_pct: 100 / 19, volume: 240000, prev_volume: 120000,
    volume_vs_previous: 2, prior_up_days: 1, trend_intensity: 1.08,
    prior_bursts_20: 0, extension_sma20_pct: 4.2, prior_day_move_pct: -0.5,
    prior_day_range_pct: 1.2, base_down4_count: 0, base_range_pct: 3.1,
    close_position: 0.8, range_expansion: 1.7,
    series: [
      { date: '2026-08-28', open: 19, high: 19.4, low: 18.8, close: 19.1, volume: 130000 },
      { date: '2026-08-31', open: 19.1, high: 19.3, low: 18.9, close: 19, volume: 120000 },
      { date: fixture.run.date, open: 19, high: 20.5, low: 18, close: 20, volume: 240000 }
    ]
  };
  const quietRow = { ...beeRow, ticker: 'QUIETBEE', gain_pct: 0.5, compression_ratio: 0.65 };
  beeData.run.stockbee = {
    version: 1, date: fixture.run.date,
    scope: { label: 'Synthetic curated universe', requested: 228, measured: 225 },
    scan: { matched: 7, shown: 2, rows: [beeRow, { ...beeRow, ticker: fixture.candidates[0].ticker }] },
    anticipation: { matched: 1, shown: 1, rows: [quietRow] },
    breadth: {
      ratios: { d5: 2.5, d10: null },
      days: ['2026-08-26', '2026-08-27', '2026-08-28', '2026-08-31', fixture.run.date]
        .map(date => ({ date, up4: 5, down4: 2, measured: 225 }))
    }
  };
  assert.equal(beeData.candidates.some(c => c.ticker === beeRow.ticker), false);
  const bee = await open(beeData), bp = bee.page;
  await bp.locator('[data-stockbee-select="TESTBEE"]').waitFor();
  assert.equal(await bp.locator('#fixture-banner').isVisible(), true);
  assert.equal(await bp.locator('#h1').textContent(), `7 base-scan matches · ${beeData.run.scored} scored reviews`);
  assert.deepEqual(await bp.locator('#stockbee-queue-breakout [data-stockbee-select]').evaluateAll(nodes => nodes.map(n => n.dataset.stockbeeSelect)), ['TESTBEE', fixture.candidates[0].ticker]);
  assert.match(await bp.locator('[data-stockbee-select="TESTBEE"]').textContent(), /Not in the scored list/);
  assert.match(await bp.locator(`[data-stockbee-select="${fixture.candidates[0].ticker}"]`).textContent(), /Also in the scored list/);
  assert.equal(await bp.locator('[data-stock-compare="TESTBEE"]').count(), 0);
  assert.match(await bp.locator('#stockbee-panel-breakout .sb-queue-heading').textContent(), /7 matches.*2 setup records/);
  assert.match(await bp.locator('#stockbee-coverage').textContent(), /Synthetic curated universe.*225 measured \/ 228 requested/);
  assert.match(await bp.locator('.sb-scope-pill').textContent(), /not the whole market/);
  assert.deepEqual(await bp.locator('.sb-pulse-stats dd').allTextContents(), ['2.50×', 'Not measured']);
  assert.equal(await bp.locator('.sb-pulse-day').count(), 5);
  assert.match(await bp.locator('.sb-pulse-day').last().getAttribute('aria-label'), /5 advances.*2 declines.*225 stocks measured/);
  pass('the canonical scan includes unscored matches and breadth stays scoped to measured subset coverage');

  await bp.locator('#stockbee-tab-breakout').focus();
  await bp.keyboard.press('ArrowRight');
  assert.equal(await bp.locator('#stockbee-tab-anticipation').getAttribute('aria-selected'), 'true');
  assert.equal(await bp.evaluate(() => document.activeElement.id), 'stockbee-tab-anticipation');
  assert.equal(await bp.locator('#stockbee-panel-breakout').isVisible(), false);
  assert.match(await bp.locator('#stockbee-rules-anticipation').textContent(), /App proxy/);
  await bp.locator('#stockbee-search').fill('quietbee');
  assert.equal(await bp.locator('#stockbee-selected-title').textContent(), 'QUIETBEE');
  await bp.locator('[data-stockbee-select="QUIETBEE"]').click();
  assert.equal(await bp.evaluate(() => document.activeElement.id), 'stockbee-selected-title');
  await bp.locator('#stockbee-search').fill('missing-setup');
  assert.equal(await bp.locator('#stockbee-panel-anticipation [data-stockbee-select]').count(), 0);
  assert.equal(await bp.locator('#stockbee-plan-setup').count(), 0);
  await bp.locator('#stockbee-panel-anticipation').getByRole('button', { name: 'Clear search', exact: true }).click();
  assert.equal(await bp.locator('#stockbee-search').inputValue(), '');
  assert.equal(await bp.evaluate(() => document.activeElement.id), 'stockbee-search');
  await bp.locator('#stockbee-tab-breakout').click();
  await bp.locator('[data-stockbee-select="TESTBEE"]').click();
  assert.equal(await bp.locator('[data-stockbee-select="TESTBEE"]').getAttribute('aria-pressed'), 'true');
  pass('anticipation stays a separate proxy list with keyboard tabs, ticker search, empty results and focused selection');

  assert.match(await bp.locator('.sb-chart svg').getAttribute('aria-label'), /TESTBEE: 3 recorded daily candles.*Last close \$20\.00/);
  assert.equal(await bp.locator('.sb-candle-body').count(), 3);
  assert.equal(await bp.locator('.sb-candle-volume').count(), 3);
  await bp.locator('.sb-candle-data > summary').click();
  assert.deepEqual(await bp.locator('.sb-bars-table tbody tr').first().locator('th,td').allTextContents(),
    [fixture.run.date, '$19.00', '$20.50', '$18.00', '$20.00', '240,000']);
  await bp.locator('.sb-candle-data > summary').click();
  await bp.locator('#stockbee-lynch-questions > summary').click();
  assert.equal(await bp.locator('.sb-lynch-item:visible').count(), 6);
  assert.deepEqual(await bp.locator('.sb-lynch-letter').allTextContents(), ['2', 'L', 'Y', 'N', 'C', 'H']);
  assert.match(await bp.locator('.sb-lynch').textContent(), /do not produce a Stockbee pass score/);
  assert.match(await bp.locator('.sb-lynch .sb-proxy').first().textContent(), /1 consecutive prior up days/);
  await bp.locator('#stockbee-lynch-questions > summary').click();
  pass('the inspector preserves exact recorded candles and six qualitative 2LYNCH questions without a fabricated score');

  await bp.locator('#bee-plan-entry').fill('99');
  await bp.locator('#bee-plan-stop').fill('90');
  await bp.locator('#stockbee-plan-setup').click();
  assert.equal(await bp.locator('#bee-plan-ticker').inputValue(), 'TESTBEE');
  assert.equal(await bp.locator('#bee-plan-entry').inputValue(), '');
  assert.equal(await bp.locator('#bee-plan-stop').inputValue(), '');
  assert.equal(await bp.locator('#bee-plan-capital').inputValue(), '');
  assert.equal(await bp.locator('#bee-plan-riskPercent').inputValue(), '');
  assert.match(await bp.locator('#bee-plan-reference').textContent(), /Historical reference only/);
  assert.ok((await bp.locator('#bee-plan-reference').textContent()).includes(fixture.run.date));
  await bp.locator('#bee-plan-use-reference').click();
  assert.equal(await bp.locator('#bee-plan-entry').inputValue(), '20');
  assert.equal(await bp.locator('#bee-plan-stop').inputValue(), '18');
  pass('setup handoff fills only the ticker until the user explicitly accepts the dated price reference');

  await bp.locator('#bee-plan-capital').fill('10000');
  await bp.locator('#bee-plan-riskPercent').fill('1');
  assert.equal(await bp.locator('#bee-plan-shares').textContent(), '50 shares');
  const planMetric = label => bp.locator('.bee-plan-metrics > div').filter({ has: bp.locator('dt', { hasText: new RegExp('^' + label + '$') }) }).locator('dd');
  assert.equal(await planMetric('Planned loss at stop').textContent(), '$100.00');
  assert.equal(await planMetric('Position cost').textContent(), '$1,000.00');
  await bp.locator('#bee-plan-cashCap').fill('600');
  assert.equal(await bp.locator('#bee-plan-shares').textContent(), '30 shares');
  assert.equal(await planMetric('Planned loss at stop').textContent(), '$60.00');
  assert.equal(await planMetric('Position cost').textContent(), '$600.00');
  assert.match(await bp.locator('.bee-plan-result-caption').textContent(), /cash cap/);
  pass('position sizing respects the entered risk budget, rounds to whole shares and applies the cash cap');

  await bp.locator('#bee-plan-stop').fill('20');
  assert.equal(await bp.locator('#bee-plan-shares').count(), 0);
  assert.match(await bp.locator('#bee-plan-result').textContent(), /stop must be below/);
  await bp.locator('#bee-plan-copy').click();
  assert.equal(await bp.locator('#bee-panel-plan').isVisible(), true);
  await bp.locator('#bee-plan-stop').fill('18');
  await bp.locator('#bee-plan-cashCap').fill('10001');
  assert.match(await bp.locator('#bee-plan-result').textContent(), /cash cap must be between zero and your capital/);
  await bp.locator('#bee-plan-cashCap').fill('19');
  assert.equal(await bp.locator('#bee-plan-shares').textContent(), '0 shares');
  await bp.locator('#bee-plan-copy').click();
  assert.match(await bp.locator('#bee-plan-notice').textContent(), /at least one whole share/);
  assert.equal(await bp.locator('.bee-journal-card').count(), 0);
  await bp.locator('#bee-plan-cashCap').fill('');
  await bp.locator('#bee-plan-riskPercent').fill('0');
  assert.equal(await bp.locator('#bee-plan-shares').textContent(), '0 shares');
  await bp.locator('#bee-plan-riskPercent').fill('1');
  pass('invalid stops, excessive cash caps and zero-share plans cannot be copied into a journal record');

  const journalNote = 'Synthetic lesson: <img src=x onerror=alert(1)> stays plain text.';
  async function writeOpenTrade(target, symbol) {
    await target.locator('#bee-journal-new').click();
    await target.locator('#bee-journal-status').selectOption('open');
    for (const [field, value] of Object.entries({ ticker: symbol, date: '2026-08-21', entry: '20', stop: '18', shares: '50' })) {
      await target.locator('#bee-journal-' + field).fill(value);
    }
    await target.locator('#bee-journal-save').click();
  }
  await bp.locator('#bee-plan-copy').click();
  assert.equal(await bp.locator('#bee-journal-status').inputValue(), 'paper');
  assert.equal(await bp.locator('#bee-journal-date').inputValue(), '');
  assert.equal(await bp.locator('.bee-journal-card').count(), 0, 'Copying a plan creates a draft only.');
  await bp.locator('#bee-journal-date').fill('2026-08-21');
  await bp.locator('#bee-journal-note').fill(journalNote);
  await bp.locator('#bee-journal-marketNote').fill('Synthetic subset only; no whole-market verdict.');
  await bp.locator('#bee-journal-save').click();
  const paperCard = bp.locator('.bee-journal-card').filter({ has: bp.locator('h4', { hasText: /^TESTBEE$/ }) });
  assert.match(await paperCard.textContent(), /Paper plan.*no holding clock or realized result/);
  assert.equal(await paperCard.locator('.bee-journal-outcome').count(), 0);
  assert.ok((await paperCard.textContent()).includes(journalNote));
  assert.equal(await bp.locator('#bee-journal-list img').count(), 0);
  await writeOpenTrade(bp, 'OPENBEE');
  let tradedCard = bp.locator('.bee-journal-card').filter({ has: bp.locator('h4', { hasText: /^OPENBEE$/ }) });
  assert.match(await tradedCard.locator('.bee-journal-clock').textContent(), /recorded sessions since entry/);
  assert.equal(await tradedCard.locator('.bee-journal-outcome').count(), 0);
  await tradedCard.getByRole('button', { name: 'Edit OPENBEE open trade', exact: true }).click();
  await bp.locator('#bee-journal-status').selectOption('closed');
  await bp.locator('#bee-journal-exit').fill('24');
  await bp.locator('#bee-journal-exitDate').fill(fixture.run.date);
  await bp.locator('#bee-journal-save').click();
  assert.match(await tradedCard.locator('.bee-journal-outcome').textContent(), /P\/L \$200\.00.*\+2\.00R before fees/);
  await writeOpenTrade(bp, 'HOLDBEE');
  assert.equal(await bp.locator('#bee-journal-summary').textContent(), '1 paper plans · 1 open trades · 1 closed trades');
  await bp.reload({ waitUntil: 'load' });
  await bp.locator('#bee-tab-journal').click();
  assert.equal(await bp.locator('.bee-journal-card').count(), 3);
  assert.ok((await paperCard.textContent()).includes(journalNote));
  assert.match(await tradedCard.locator('.bee-journal-outcome').textContent(), /\+2\.00R/);
  const storedJournal = await bp.evaluate(() => JSON.parse(localStorage.getItem('spicystock.trade-journal.v1')));
  assert.deepEqual(storedJournal.records.map(record => record.status).sort(), ['closed', 'open', 'paper']);
  assert.equal(storedJournal.records.find(record => record.ticker === 'TESTBEE').exit, null);
  assert.equal(storedJournal.records.find(record => record.ticker === 'OPENBEE').stop, 18);
  pass('paper, open and closed records remain distinct; exact R uses the initial stop and plain-text notes survive reload');

  for (const mode of ['corrupt', 'blocked']) {
    const temporary = await open(beeData, mode === 'corrupt' ? () => {
      localStorage.setItem('spicystock.trade-journal.v1', '{"version":1,"records":"bad"}');
    } : () => {
      const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
      Storage.prototype.getItem = function (key) { if (key === 'spicystock.trade-journal.v1') throw new DOMException('Blocked', 'SecurityError'); return get.call(this, key); };
      Storage.prototype.setItem = function (key, value) { if (key === 'spicystock.trade-journal.v1') throw new DOMException('Blocked', 'SecurityError'); return set.call(this, key, value); };
    });
    await temporary.page.locator('#bee-tab-journal').click();
    await writeOpenTrade(temporary.page, 'MEMORYBEE');
    assert.equal(await temporary.page.locator('.bee-journal-card').count(), 1);
    assert.match(await temporary.page.locator('#bee-journal-storage').textContent(), /^Only this visit/);
    assert.match(await temporary.page.locator('#bee-plan-notice').textContent(), /for this visit only/);
    if (mode === 'corrupt') assert.equal(await temporary.page.evaluate(() => localStorage.getItem('spicystock.trade-journal.v1')), '{"version":1,"records":"bad"}');
    assert.equal(await temporary.page.locator('#stockbee-search').isEnabled(), true);
    await temporary.context.close();
  }
  pass('unreadable or blocked journal storage preserves the stored copy and keeps a clearly temporary journal usable');

  async function assertBeeGeometry() {
    const problems = await bp.evaluate(() => {
      const issues = [];
      if (document.documentElement.scrollWidth > innerWidth + 1) issues.push('page overflow');
      for (const section of document.querySelectorAll('#stockbee-workspace, #stockbee-plan')) {
        const outer = section.getBoundingClientRect();
        if (outer.left < -2 || outer.right > innerWidth + 2) issues.push(section.id + ' outside viewport');
        for (const control of section.querySelectorAll('button,input,select,textarea,summary,svg')) {
          if (!control.getClientRects().length || control.closest('[hidden]')) continue;
          const box = control.getBoundingClientRect();
          if (box.left < outer.left - 2 || box.right > outer.right + 2) issues.push((control.id || control.tagName) + ' outside card');
          if (control.tagName.toLowerCase() !== 'svg' && box.height < 43.5) issues.push((control.id || control.tagName) + ' below 44px touch height');
        }
      }
      return issues;
    });
    assert.deepEqual(problems, [], 'Stockbee workbench and planner controls must fit the phone.');
  }
  for (const width of [320, 390]) {
    await bp.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      await bp.locator(`.sc-theme-toggle [data-theme="${theme}"]`).click();
      await bp.locator('#bee-tab-plan').click();
      for (const [field, value] of Object.entries({ ticker: 'TESTBEE', capital: '10000', riskPercent: '1', entry: '20', stop: '18', cashCap: '600' })) {
        await bp.locator('#bee-plan-' + field).fill(value);
      }
      await assertBeeGeometry();
      await screenshot(bp, '#stockbee-title', `stockbee-workbench-${width}-${theme}`);
      await screenshot(bp, '#stockbee-selected-title', `stockbee-inspector-${width}-${theme}`);
      await screenshot(bp, '#bee-plan-ticker', `stockbee-planner-${width}-${theme}`);
      await bp.locator('#bee-tab-journal').click();
      await assertBeeGeometry();
      await screenshot(bp, '#bee-journal-list', `stockbee-journal-${width}-${theme}`);
    }
  }
  await bee.context.close();
  pass('workbench, inspector, risk planner and journal fit 320px and 390px phones in both themes with usable touch controls');
  assert.deepEqual(errors, [], 'No browser exceptions during research interactions.');
  pass('research interactions complete without application exceptions');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
console.log(`${checks} research cockpit checks passed`);
