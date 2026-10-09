/* A closed scan defers only presentation. The loaded record, its criteria,
   legacy routes and the native disclosure remain the authorities. */
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
const NOW = '2026-09-10T22:31:00Z';

export async function checkDeferredScan({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- deferred scan: native disclosure, current record and legacy destinations');
  const countRows = page => page.locator('#scan-table tbody tr').count();
  const ready = (page, count) => page.waitForFunction(count => document.querySelectorAll('#scan-table tbody tr').length === count, count);
  const render = (page, record) => page.evaluate(record => SCStock.render(record, new Date('2026-09-10T22:31:00Z')), record);
  const scores = page => page.locator('#scan-table tbody tr').evaluateAll(rows => rows.map(row => +row.dataset.score));

  for (const width of [1280, 390]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { reducedMotion: 'reduce' });
    try {
      eq(`${width}: scan starts closed`, await page.locator('#scan').evaluate(node => node.open), false);
      eq(`${width}: closed scan builds no table or evidence controls`, await page.locator('#scan-table, #scan .ss-signal-detail').count(), 0);
      check(`${width}: deferred summary still gives the full count`, (await page.locator('#scan-summary').textContent()).includes(`${data.bursts.length} bursts`));
      const original = await page.evaluate(() => JSON.stringify(SCStock.data));
      const recordRequests = [];
      page.on('request', request => { if (/\.json(?:\?|$)/.test(request.url()) && !request.url().includes('api.github.com')) recordRequests.push(request.url()); });
      await page.locator('#scan-summary').focus();
      await page.keyboard.press('Enter');
      await ready(page, data.bursts.length);
      eq(`${width}: native keyboard opening hydrates every row`, await countRows(page), data.bursts.length);
      eq(`${width}: every recorded criterion has evidence`, await page.locator('#scan .ss-signal-detail').count(), data.bursts.reduce((n, b) => n + b.quality.checks.length, 0));
      eq(`${width}: opening uses the record already loaded`, recordRequests, []);
      eq(`${width}: hydration leaves publication unchanged`, await page.evaluate(() => JSON.stringify(SCStock.data)), original);
      await page.waitForFunction(() => !!document.querySelector('#scan [data-sc-matrix-controls] button'));
      eq(`${width}: one matrix navigator is attached`, await page.locator('#scan [data-sc-matrix-controls]').count(), 1);
      const region = page.locator('#scan .sc-table-scroll');
      await region.evaluate(node => { node.scrollLeft = 0; });
      await region.focus();
      await page.keyboard.press('ArrowRight');
      await page.waitForFunction(() => document.querySelector('#scan .sc-table-scroll').scrollLeft > 0);
      check(`${width}: hydrated matrix scrolls with keyboard`, await region.evaluate(node => node.scrollLeft > 0));
      await region.evaluate(node => { node.scrollLeft = 0; });
      await page.locator('#scan [data-sc-matrix-column]').last().click();
      check(`${width}: criterion navigation exposes grade`, await region.evaluate(node => {
        const grade = node.querySelector('thead th:last-child').getBoundingClientRect(), port = node.getBoundingClientRect();
        return node.scrollLeft > 0 && grade.left >= port.left && grade.right <= port.right + 1;
      }));
      const sort = page.locator('#scan-table .sc-table__sort');
      await sort.focus(); await page.keyboard.press('Enter');
      const ascending = await scores(page);
      check(`${width}: hydrated score sort is ascending`, ascending.every((n, i) => i === 0 || ascending[i - 1] <= n), ascending.join(','));
      eq(`${width}: sort announces direction`, await sort.locator('..').getAttribute('aria-sort'), 'ascending');
      const ticker = data.bursts[0].ticker;
      const evidence = page.locator(`#burst-${ticker} .ss-signal-detail`).first();
      await evidence.locator('summary').focus(); await page.keyboard.press('Enter');
      eq(`${width}: evidence opens with keyboard`, await evidence.evaluate(node => node.open), true);
      check(`${width}: opened evidence prints recorded observation and rule`, (await evidence.textContent()).includes('Observed:') && (await evidence.textContent()).includes('Recorded rule:'));
      await page.evaluate(() => { window.__scanTable = document.getElementById('scan-table'); });
      await page.locator('#scan-summary').click();
      await page.locator('#scan-summary').click();
      await ready(page, data.bursts.length);
      eq(`${width}: reopen keeps the same table`, await page.evaluate(() => window.__scanTable === document.getElementById('scan-table')), true);
      eq(`${width}: reopen preserves sort`, await scores(page), ascending);
      eq(`${width}: reopen preserves expanded evidence`, await evidence.evaluate(node => node.open), true);
      eq(`${width}: reopen does not duplicate controls`, await page.locator('#scan [data-sc-matrix-controls]').count(), 1);
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.screenshot({ path: path.join(shotsDir, `scan-open-${width}.png`) });
      }

      // The old matrix must disappear before a newer closed record is opened.
      await page.locator('#scan-summary').click();
      const revision = structuredClone(data);
      revision.bursts = [structuredClone(data.bursts[0])];
      revision.bursts[0].ticker = 'NEWSCAN';
      revision.bursts[0].quality.checks[0].display = 'revision-only observation';
      revision.trades = [];
      revision.closest_miss = { sentence: 'The current revision is the closest miss.' };
      await render(page, revision);
      eq(`${width}: closed refresh discards previous rows`, await countRows(page), 0);
      eq(`${width}: refresh does not open the disclosure`, await page.locator('#scan').evaluate(node => node.open), false);
      await page.locator('#scan-summary').click(); await ready(page, 1);
      eq(`${width}: next open uses current symbols`, await page.locator('#scan-table tbody tr').evaluateAll(rows => rows.map(row => row.dataset.ticker)), ['NEWSCAN']);
      check(`${width}: next open uses current evidence`, (await page.locator('#scan-table').textContent()).includes('revision-only observation'));
      eq(`${width}: no old rows remain after refresh`, await page.locator(`#burst-${ticker}`).count(), 0);
      const sameObject = await page.evaluate(() => {
        const record = SCStock.data;
        record.bursts[0].ticker = 'SAMEOBJECT';
        record.bursts[0].quality.checks[0].display = 'same-object observation';
        SCStock.render(record, new Date('2026-09-10T22:31:00Z'));
        return Array.from(document.querySelectorAll('#scan-table tbody tr')).map(row => row.dataset.ticker);
      });
      eq(`${width}: open refresh synchronously rebuilds even the same record object`, sameObject, ['SAMEOBJECT']);
      check(`${width}: same-object refresh uses new evidence`, (await page.locator('#scan-table').textContent()).includes('same-object observation'));
      await page.locator('#scan-summary').click();
      // Toggle is queued: the latest render must win before that event arrives.
      await page.evaluate(record => {
        document.getElementById('scan').open = true;
        SCStock.render(record, new Date('2026-09-10T22:31:00Z'));
      }, data);
      await ready(page, data.bursts.length);
      eq(`${width}: queued opening cannot restore previous publication`, await page.locator('#burst-NEWSCAN, #burst-SAMEOBJECT').count(), 0);
      await page.locator(`#burst-${ticker} button[data-go]`).click();
      await page.waitForFunction(ticker => document.getElementById('detail-h2').textContent === ticker, ticker);
      eq(`${width}: hydrated row selects its stock`, await page.locator('#detail-h2').textContent(), ticker);
      eq(`${width}: hydrated row moves focus to detail`, await page.evaluate(() => document.activeElement.id), 'detail');
      await render(page, { ...data, bursts: [], trades: [], closest_miss: null });
      eq(`${width}: open empty record has no stale table`, await countRows(page), 0);
      check(`${width}: open empty record explains itself`, (await page.locator('#scan-body').textContent()).includes('The scan found no burst'));
      eq(`${width}: deferred scan page errors`, errors, []);
    } finally { await context.close(); }
  }

  for (const hash of ['#scan', '#scan-details', '#closest-miss', `#burst-${data.bursts[0].ticker}`, `#trade-${data.bursts[0].ticker}`]) {
    const scanRoute = ['#scan', '#scan-details', '#closest-miss'].includes(hash);
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/notrade.json', NOW, 390, { hash, reducedMotion: 'reduce' });
    try {
      eq(`${hash}: legacy route opens only its destination`, await page.locator('#scan').evaluate(node => node.open), scanRoute);
      if (scanRoute) check(`${hash}: legacy scan is hydrated`, await countRows(page) > 0);
      else {
        eq(`${hash}: stock deep link keeps scan deferred`, await countRows(page), 0);
        eq(`${hash}: stock deep link opens requested detail`, await page.locator('#detail-h2').textContent(), data.bursts[0].ticker);
      }
      if (hash === '#closest-miss') check('legacy closest miss is revealed and scrolled into view', await page.locator('#closest-miss').evaluate(node => {
        const box = node.getBoundingClientRect(); return box.height > 0 && box.top >= -1 && box.top < innerHeight;
      }));
      eq(`${hash}: legacy browser errors`, errors, []);
    } finally { await context.close(); }
  }
}
