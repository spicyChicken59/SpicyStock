// Browser interactions for the research cockpit. Everything is served from this
// checkout, including explicitly labelled fixtures; no market service is called.
// node tools/research_cockpit_smoke.mjs [--shots /tmp/research-shots]
import assert from 'node:assert/strict';
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
  await page.getByRole('button', { name: `Remove ${choices[0]} from comparison`, exact: true }).click();
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
  assert.deepEqual(errors, [], 'No browser exceptions during research interactions.');
  pass('research interactions complete without application exceptions');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
console.log(`${checks} research cockpit checks passed`);
