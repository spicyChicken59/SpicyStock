import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { gunzipSync, gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NOW = '2026-09-10T22:31:00Z';
// Browser journeys for the recorded action summary and explicit chart inspection.
// Called by page_smoke; all market inputs are committed offline fixtures.
export async function checkActionability({ browser, base, data, open, check, eq, shotsDir, coreOnly }) {
  console.log('-- burst actionability and recorded charts');
  const ticket = data.bursts.find(b => data.trades.includes(b.ticker));
  const app = await open(browser, base, '/tests/fixtures/page/full.json', '2026-09-10T22:31:00Z', 1280,
    { hash: '#/explore/bursts/' + ticket.ticker });
  const { page } = app;
  const metrics = { initialEvidenceRequests: 0, recoveredChartRequests: 0, chartHeights: { desktop: 400, mobile: 300 }, publicationBytesAdded: 0 };
  if (shotsDir) { await mkdir(shotsDir, {recursive:true}); await page.screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, 'action-first-screen-1280-dark.png')}); }
  const values = await page.locator('#detail [data-plan-value]').evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.dataset.planValue, n.textContent])));
  const money = n => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const order = ticket.plan.order_json;
  eq('action summary prints exact recorded ticket fields', values, {
    trigger: money(order.stop_price), limit: money(order.limit_price), stop: money(order.then.stop_price), shares: order.quantity + ' shares'
  });
  check('action summary precedes the chart', await page.evaluate(() => !!(document.querySelector('#detail .ss-action').compareDocumentPosition(document.querySelector('#detail .ss-chart-panel')) & Node.DOCUMENT_POSITION_FOLLOWING)));
  check('action summary names its applicable session', (await page.locator('#detail .ss-action').innerText()).includes(data.run.timing.applicable_session));
  eq('plan details starts closed', await page.locator('#disc-plan').evaluate(n => n.open), false);
  await page.locator('#detail .ss-action [data-copy]').focus(); await page.keyboard.press('Enter');
  eq('copy uses the same recorded ticket as the existing order block', await page.evaluate(() => navigator.clipboard.readText()),
    await page.locator('#disc-plan [data-order]').textContent());
  await page.locator('#detail .ss-action [data-open]').focus(); await page.keyboard.press('Enter');
  eq('keyboard opens and focuses existing plan details', await page.evaluate(() => [document.querySelector('#disc-plan').open, document.activeElement === document.querySelector('#disc-plan summary')]), [true, true]);
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.querySelector('.ss-action [data-open]').getAttribute('aria-expanded') === 'false');
  check('material risk adjustment remains explained', (await page.locator('[data-sizing-note]').innerText()).includes(ticket.plan.stop_risk_reason));
  const geometry = pg => pg.locator('#chart-mount .sc-chart--stock').evaluate(n => {
    const g = n.geometry(); return { dates: g.bars.map(b => b.date), prices: [...n.querySelectorAll('[data-level]')].map(x => [x.dataset.level, x.getAttribute('y1')]) };
  });
  await page.locator('#detail .sc-tab[data-range="120"]').click();
  const original = await geometry(page), preference = await page.evaluate(() => localStorage.getItem('spicystock:chart:v1'));
  await page.locator('#detail .ss-evidence [data-anchor="burst"]').click();
  eq('explicit evidence focus is available', await page.locator('#detail [data-evidence-focus]').count(), 1);
  eq('selecting evidence does not change chart geometry', await geometry(page), original);
  await page.locator('[data-evidence-focus]').focus(); await page.keyboard.press('Enter');
  const focused = await geometry(page);
  eq('burst focus shows 21 actual sessions including the signal', [focused.dates.length, focused.dates.at(-1)], [21, data.run.session]);
  eq('focus retains its evidence marker', await page.locator('#chart-mount .sc-chart--stock').getAttribute('data-highlight'), data.run.session);
  eq('focus leaves the persisted range untouched', await page.evaluate(() => localStorage.getItem('spicystock:chart:v1')), preference);
  eq('focus retains every recorded price level', focused.prices.map(p => p[0]), original.prices.map(p => p[0]));
  await page.locator('#detail .ss-evidence [data-anchor="prior"]').click();
  eq('selecting a different marker even while focused does not zoom', await geometry(page), focused);
  await page.locator('[data-evidence-focus]').click();
  const prior = await geometry(page);
  check('prior focus has useful context and includes that session', prior.dates.length >= 21 && prior.dates.includes(ticket.series.at(-2).date));
  await page.locator('[data-evidence-restore]').focus(); await page.keyboard.press('Enter');
  eq('restore returns to the prior geometry', await geometry(page), original);
  eq('restoring focus returns keyboard focus to the evidence action', await page.evaluate(() => document.activeElement.hasAttribute('data-evidence-focus')), true);
  await page.locator('#detail .ss-evidence [data-anchor="base"]').click();
  await page.locator('[data-evidence-focus]').click();
  const baseDates = (await geometry(page)).dates, qbase = ticket.quality.base;
  check('base focus includes the full base and context', baseDates.includes(qbase.start) && baseDates.includes(qbase.end) && baseDates[0] < qbase.start && baseDates.at(-1) > qbase.end);
  await page.locator('#detail .sc-tab[data-range="setup"]').click();
  eq('choosing a normal range ends temporary focus', await page.locator('[data-evidence-restore]').isVisible(), false);
  check('retained source reader is available', await page.evaluate(() => typeof SCStock.loadSourceChart === 'function'));
  if (shotsDir) { await mkdir(shotsDir, {recursive:true}); await page.locator('#detail').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, 'action-ticket-1280-dark.png')}); }
  eq('actionability page errors', [...app.errors], []);
  await app.context.close();

  if (coreOnly) return;

  const launch = async (input, options = {}, respond) => {
    const requests = [];
    const opened = await open(browser, base, '/tests/fixtures/page/full.json', options.now || NOW, options.width || 1280, {
      hash: '#/explore/bursts/' + (options.ticker || ticket.ticker), lens: 'all', ...options,
      beforeLoad: async pg => {
        await pg.route('**/tests/fixtures/page/full.json', route => route.fulfill({json: input}));
        pg.on('request', request => { if (/\/evidence\/.*\.json\.gz/.test(request.url())) requests.push(request.url()); });
        if (respond) await pg.route('**/docs/evidence/*.json.gz', respond);
      }
    });
    return {...opened, requests};
  };
  const closed = async (opened, label) => { eq(label + ': no unexpected browser errors', [...opened.errors], []); await opened.context.close(); };
  const earlier = structuredClone(data), earlyBase = earlier.bursts[0].quality.base;
  earlyBase.start = ticket.series[10].date; earlyBase.end = ticket.series[15].date;
  const early = await launch(earlier);
  await early.page.locator('#detail .sc-tab[data-range="60"]').click();
  const earlyBefore = await geometry(early.page);
  await early.page.locator('#detail .ss-evidence [data-anchor="base"]').click();
  eq('out-of-range selection still leaves the range alone', await geometry(early.page), earlyBefore);
  await early.page.locator('[data-evidence-focus]').click();
  check('explicit focus reaches earlier retained evidence', (await geometry(early.page)).dates.includes(earlyBase.start));
  eq('focus before the signal never labels its last bar a burst', await early.page.locator('#chart-mount .sc-chart--stock').evaluate(n => n.geometry().burst), null);
  check('earlier focus preserves the recorded trigger and stop', (await geometry(early.page)).prices.some(p => p[0] === 'trigger') && (await geometry(early.page)).prices.some(p => p[0] === 'stop'));
  await early.page.locator('[data-evidence-restore]').click(); eq('earlier focus restores 60-session geometry', await geometry(early.page), earlyBefore);
  await closed(early, 'earlier focus');
  for (const name of ['full', 'red', 'yellow', 'degraded']) {
    const input = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/' + name + '.json')));
    const a = await launch(input);
    for (const row of input.bursts) {
      await a.page.evaluate(ticker => { location.hash = '#/explore/bursts/' + ticker; }, row.ticker);
      await a.page.waitForFunction(ticker => document.querySelector('#detail').dataset.selected === 'bursts:' + ticker, row.ticker);
      const block = a.page.locator('#detail .ss-action'), has = (await block.getAttribute('data-ticket')) === 'order';
      eq(name + ' ' + row.ticker + ': levels only for a usable recorded ticket', await block.locator('[data-plan-value]').count(), has ? 4 : 0);
      if (!has) {
        eq(name + ' ' + row.ticker + ': explicit no-entry heading', await block.locator('h3').innerText(), 'No SpicyStock entry for this setup');
        check(name + ' ' + row.ticker + ': actual refusal is present', (await block.locator('[data-no-entry-reason]').innerText()).length > 15);
        eq(name + ' ' + row.ticker + ': no synthetic copy control', await block.locator('[data-copy]').count(), 0);
      }
    }
    await closed(a, name + ' action truth table');
  }
  for (const [name, now] of [['expired', '2026-09-11T15:00:00Z'], ['stale', '2026-09-16T14:00:00Z']]) {
    const a = await launch(data, {now});
    eq(name + ': no actionable levels or copy', await a.page.locator('.ss-action [data-plan-value], .ss-action [data-copy]').count(), 0);
    check(name + ': refusal names timing/publication', /ended|stale/.test(await a.page.locator('[data-no-entry-reason]').innerText()));
    await a.page.locator('.ss-action [data-open]').click();
    check(name + ': historical plan starts with refusal', (await a.page.locator('#disc-plan .sc-disclosure__body > p').first().innerText()).startsWith('Recorded plan for inspection. No SpicyStock entry'));
    if (shotsDir) await a.page.locator('#detail').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, 'action-' + name + '-1280.png')});
    await closed(a, name);
  }
  for (const [kind, reason] of [['no_shares', 'no whole share after the recorded allocation'], ['equity', 'beyond the configured equity'], ['slot_cap', 'beyond the slot cap']]) {
    const input = structuredClone(data); input.trades = [];
    input.cash_budget.cut = [{ticker:ticket.ticker, kind, reason}];
    const a = await launch(input);
    eq(kind + ': actual cut reason is immediate', await a.page.locator('[data-no-entry-reason]').innerText(), reason[0].toUpperCase() + reason.slice(1) + '.');
    eq(kind + ': even a retained plan does not invent an entry', await a.page.locator('.ss-action [data-plan-value]').count(), 0);
    await closed(a, kind);
  }

  // Real retained fixture frame, only its browser-series omission is simulated.
  const uncharted = structuredClone(data), missing = uncharted.bursts.find(b => b.ticker === 'DLLR'); missing.series = [];
  const key = missing.evidence.source.sha256;
  const bytes = await readFile(path.join(ROOT, 'tests/fixtures/provenance/objects/' + key + '.json.gz'));
  const source = JSON.parse(gunzipSync(bytes));
  const a = await launch(uncharted, {}, async route => {
    await new Promise(resolve => setTimeout(resolve, 180));
    await route.fulfill({status: 200, contentType: 'application/gzip', body: bytes});
  });
  eq('cards and normal initial selection request no source evidence', a.requests.length, 0);
  metrics.initialEvidenceRequests = a.requests.length;
  await a.page.evaluate(() => { location.hash = '#/explore/bursts/DLLR'; });
  await a.page.waitForSelector('[data-load-chart]');
  eq('selecting the uncharted stock is still request-free until asked', a.requests.length, 0);
  metrics.selectedMissingStockRequests = a.requests.length;
  await a.page.locator('#detail [data-follow-action="add"]').click();
  await a.page.waitForFunction(() => SCStock.follow.list().some(item => item.ticker === 'DLLR'));
  const savedBefore = await a.page.evaluate(() => JSON.stringify(SCStock.follow.list()));
  await a.page.locator('[data-load-chart]').focus(); await a.page.keyboard.press('Enter');
  await a.page.waitForSelector('[data-chart-recovery="loading"][aria-busy="true"]');
  await a.page.waitForSelector('[data-chart-recovery="loaded"][aria-busy="false"]');
  check('keyboard chart load leaves focus in chart controls', await a.page.evaluate(() => !!document.activeElement.closest('.ss-chart-panel')));
  eq('one explicit request loads the exact content-addressed object', a.requests.map(url => url.split('/').at(-1)), [key + '.json.gz']);
  check('the loaded chart states source identity honestly', (await a.page.locator('[data-chart-source]').innerText()).includes('Recorded source evidence · source hash verified'));
  await a.page.locator('#detail .sc-tab[data-range="120"]').click();
  eq('chart dates are the exact retained last 120, never newer bars', (await geometry(a.page)).dates, source.dates.slice(-120));
  eq('source numeric precision is preserved', await a.page.locator('#chart-mount .sc-chart--stock').evaluate(n => n.geometry().bars.map(b => b.c)), source.values[3].slice(-120));
  eq('loading a chart never overwrites an already saved original', await a.page.evaluate(() => JSON.stringify(SCStock.follow.list())), savedBefore);
  await a.page.evaluate(ticker => { location.hash = '#/explore/bursts/' + ticker; }, ticket.ticker);
  await a.page.waitForFunction(ticker => document.querySelector('#detail').dataset.selected === 'bursts:' + ticker, ticket.ticker);
  await a.page.evaluate(() => { history.back(); });
  await a.page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'bursts:DLLR');
  eq('Back returns the recovered chart without another request', [a.requests.length, await a.page.locator('#chart-mount .sc-chart--stock').count()], [1, 1]);
  metrics.repeatSelectionExtraRequests = a.requests.length - 1;
  await a.page.locator('#detail [data-pin]').click();
  await a.page.locator(`#pick-list [data-pin="bursts:${ticket.ticker}"]`).click();
  await a.page.locator('#compare-open').click();
  eq('Compare can reuse the chart without depending on another fetch', [a.requests.length, await a.page.locator('#compare .sc-chart--stock').count()], [1, 2]);
  await a.page.keyboard.press('Escape');
  metrics.recoveredChartRequests = a.requests.length; metrics.sourceGzipBytes = bytes.length; metrics.sourceRawBytes = gunzipSync(bytes).length;
  if (shotsDir) await a.page.locator('#detail').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, 'action-recovered-1280.png')});
  await closed(a, 'lazy chart success');

  for (const kind of ['legacy', 'wrong-reference', 'bad-hash', 'network']) {
    const input = structuredClone(uncharted), row = input.bursts.find(b => b.ticker === 'DLLR');
    if (kind === 'legacy') delete row.evidence;
    if (kind === 'wrong-reference') row.evidence.session = '2026-09-09';
    let broken = structuredClone(source); broken.values[3][0] += 1;
    const f = await launch(input, {ticker:'DLLR'}, route => kind === 'network' ? route.fulfill({status:503, body:'unavailable'}) : route.fulfill({status:200, body:gzipSync(JSON.stringify(broken))}));
    if (kind === 'legacy' || kind === 'wrong-reference') {
      eq(kind + ': no fabricated chart or recovery request', [await f.page.locator('[data-load-chart]').count(), f.requests.length], [0, 0]);
      check(kind + ': honest unavailable state', (await f.page.locator('#chart-mount').innerText()).includes('Chart unavailable'));
    } else {
      await f.page.locator('[data-load-chart]').click(); await f.page.waitForSelector('[data-chart-recovery="failed"]');
      check(kind + ': failure leaves the stock usable', (await f.page.locator('[data-chart-load-status]').innerText()).includes('plan remain available'));
      eq(kind + ': no chart used on failure', await f.page.locator('#chart-mount .sc-chart--stock').count(), 0);
      await f.page.locator('.ss-action [data-open]').click(); eq(kind + ': conditions can still open', await f.page.locator('#disc-checklist').evaluate(n => n.open), true);
      await f.page.locator('#detail [data-follow-action="add"]').click();
      await f.page.waitForFunction(() => SCStock.follow.list().length === 1);
      eq(kind + ': save still works', await f.page.evaluate(() => SCStock.follow.list().length), 1);
    }
    if (kind === 'bad-hash') {
      await f.page.unroute('**/docs/evidence/*.json.gz');
      await f.page.route('**/docs/evidence/*.json.gz', route => route.fulfill({status:200, body:bytes}));
      await f.page.locator('[data-load-chart]').click(); await f.page.waitForSelector('[data-chart-recovery="loaded"]');
      eq('failed evidence may be retried successfully', f.requests.length, 2);
    }
    if (kind === 'network') { check('expected HTTP failure has no uncaught script error', ![...f.errors].some(e => e.startsWith('pageerror'))); await f.context.close(); }
    else await closed(f, kind);
  }

  const race = await launch(uncharted, {ticker:'DLLR'}, async route => {
    await new Promise(resolve => setTimeout(resolve, 350)); await route.fulfill({status:200, body:bytes});
  });
  await race.page.locator('[data-load-chart]').click();
  await race.page.evaluate(ticker => { location.hash = '#/explore/bursts/' + ticker; }, ticket.ticker);
  await race.page.waitForTimeout(500);
  eq('a late source response cannot replace another selection', await race.page.locator('#chart-mount .sc-chart--stock').getAttribute('data-ticker'), ticket.ticker);
  await race.page.evaluate(() => { history.back(); }); await race.page.waitForSelector('[data-load-chart]');
  await race.page.locator('[data-load-chart]').click(); await race.page.waitForSelector('[data-chart-recovery="loaded"]');
  eq('a disposed panel response is cached for a later explicit request', race.requests.length, 1);
  await closed(race, 'late response');

  const missingTicket = structuredClone(data); missingTicket.bursts[0].series = [];
  const failedTicket = await launch(missingTicket, {}, route => route.fulfill({status:200, body:'invalid source'}));
  await failedTicket.page.locator('[data-load-chart]').click(); await failedTicket.page.waitForSelector('[data-chart-recovery="failed"]');
  eq('failed chart does not withdraw a valid recorded ticket', await failedTicket.page.locator('.ss-action [data-plan-value]').count(), 4);
  await failedTicket.page.locator('.ss-action [data-copy]').click();
  eq('failed chart still permits the exact guarded order copy', await failedTicket.page.evaluate(() => navigator.clipboard.readText()), await failedTicket.page.locator('#disc-plan [data-order]').textContent());
  await closed(failedTicket, 'ticket with failed chart');

  // Both themes at all requested sizes; inspect the screenshots as well as bounds.
  for (const width of [1280, 390, 320]) for (const theme of ['dark', 'light']) {
    const m = await launch(data, {width, theme, touch:width < 600});
    const bounds = await m.page.locator('#detail').evaluate(node => {
      const rect = node.getBoundingClientRect();
      const parts = [...node.querySelectorAll('.ss-action [data-plan-value], .ss-action__controls button, .ss-action__head')];
      return {overflow: document.documentElement.scrollWidth > innerWidth,
        contained: parts.every(n => { const r = n.getBoundingClientRect(); return r.left >= rect.left && r.right <= rect.right + 1; }),
        targets: [...node.querySelectorAll('.ss-action__controls button')].map(n => n.getBoundingClientRect().height)};
    });
    check(width + ' ' + theme + ': plan fits without overflow', !bounds.overflow && bounds.contained, bounds);
    if (width < 600) check(width + ' ' + theme + ': action touch targets', bounds.targets.every(h => h >= 44), bounds);
    if (shotsDir) await m.page.locator('#detail').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, `action-ticket-${width}-${theme}.png`)});
    await m.page.locator('#detail .ss-evidence [data-anchor="burst"]').click(); await m.page.locator('[data-evidence-focus]').focus(); await m.page.keyboard.press('Enter');
    eq(width + ' ' + theme + ': keyboard focus works', await m.page.locator('#detail .ss-chart-panel').getAttribute('data-focus'), 'burst');
    if (shotsDir) await m.page.locator('#detail .ss-chart-panel').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, `action-focus-${width}-${theme}.png`)});
    await m.page.locator('[data-evidence-restore]').click();
    eq(width + ' ' + theme + ': restore keeps setup preference', await m.page.locator('#chart-mount .sc-chart--stock').getAttribute('data-range'), 'setup');
    await m.page.evaluate(ticker => { location.hash = '#/explore/bursts/' + ticker; }, data.bursts[1].ticker);
    await m.page.waitForFunction(ticker => document.querySelector('#detail').dataset.selected === 'bursts:' + ticker, data.bursts[1].ticker);
    if (shotsDir) await m.page.locator('#detail').screenshot({style:'.sc-masthead { visibility: hidden; }', path:path.join(shotsDir, `action-no-ticket-${width}-${theme}.png`)});
    await closed(m, width + ' ' + theme);
  }
  if (shotsDir) await writeFile(path.join(shotsDir, 'actionability-measurements.json'), JSON.stringify(metrics, null, 2) + '\n');
}
