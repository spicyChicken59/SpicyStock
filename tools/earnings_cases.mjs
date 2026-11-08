/* The earnings warning on the page is the record's own row, printed: each
   ticket's run.earnings sentence verbatim in the stock's risk item and under
   the tickets sheet, the block's sentence in Method. A record made before the
   block says no report date was checked, and a row or block the page cannot
   read is never read as clear. A warning and never a refusal: the ticket
   stands beside it. Under version 2 each row also carries the ticket's recent
   SEC current-report items (src/earnings_risk.py items_of), printed verbatim
   under the earnings sentence; a version-1 record says the check predates it,
   and a row without a readable items sentence is never read as no item.
   Lane B: writes no scratch record, reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const FIXTURES = path.resolve('tests/fixtures/page');
const clone = (d) => JSON.parse(JSON.stringify(d));
const BEFORE = 'Earnings date not checked: this record predates the earnings warning.';
const UNREAD = 'Earnings date not established: this record carries no readable earnings row for this ticket.';
const ITEMS_V1 = 'Recent SEC current reports not checked: this record predates the check.';
const ITEMS_UNREAD = 'Recent SEC current reports not established: this record carries no readable current-report row for this ticket.';

// a record served from memory in place of a fixture, so a shape the generator
// never writes can be put in front of the page
function routed(name, record) {
  const body = JSON.stringify(record);
  return { url: `/earnings-${name}.json`, beforeLoad: (p) => p.route(`**/earnings-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) };
}
const riskOf = async (page) => (await page.locator('.ss-decision [data-item="risk"]').count())
  ? page.locator('.ss-decision [data-item="risk"]').innerText() : '';
const methodOf = (page) => page.locator('#run-meta').evaluate((n) => n.textContent);

export async function checkEarnings({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- earnings: each ticket\'s warning, printed from the record');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const degraded = JSON.parse(await readFile(path.join(FIXTURES, 'degraded.json'), 'utf8'));
  const row = full.run.earnings.rows.find((r) => r.ticker === 'AAPL');
  check('the full fixture carries AAPL\'s warning, estimated inside its hold', !!row && row.verdict === 'estimate_inside' && full.trades.includes('AAPL'), JSON.stringify(row && row.verdict));
  check('and AMD, cut by the slot cap, carries none', !full.run.earnings.rows.some((r) => r.ticker === 'AMD') && full.beyond_cap.includes('AMD'));
  // version 2: AAPL's row carries a material current report (an 8-K item 1.01 two days before the signal)
  check('the full fixture is a version-2 block whose AAPL row names a material item', full.run.earnings.version === 2 && !!row.items && row.items.status === 'material' && row.items.material.map((m) => m.item).join() === '1.01', JSON.stringify(row.items && row.items.status));
  check('the items sentence names the item by its heading and says it is not a refusal', /8-K item 1\.01 \(Entry into a Material Definitive Agreement\)/.test(row.items.sentence) && /not a refusal/.test(row.items.sentence) && /read it before entry/.test(row.items.sentence), row.items.sentence);

  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [320, 'dark']]) {
    const where = `${width} ${theme}`, height = width < 400 ? 844 : 900;
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width,
      { height, theme, reducedMotion: 'reduce', lens: 'all', hash: '#/explore/bursts/AAPL' });
    try {
      const risk = await riskOf(page);
      check(`${where}: AAPL's risk item prints its earnings row verbatim`, risk.includes(row.sentence), risk);
      eq(`${where}: once`, risk.split(row.sentence).length - 1, 1);
      check(`${where}: the sentence says it is an estimate and not an announced date`, row.sentence.includes('not an announced date'));
      check(`${where}: AAPL's risk item prints its current-report items verbatim, under the earnings sentence`, risk.includes(row.items.sentence) && risk.indexOf(row.sentence) < risk.indexOf(row.items.sentence), risk);
      eq(`${where}: the items sentence once`, risk.split(row.items.sentence).length - 1, 1);
      // a warning, never a refusal: the stock is still a ticket and the sheet still offers it
      check(`${where}: the ticket still stands beside it`, (await page.locator('#orders-summary').innerText()).includes('1 order'), await page.locator('#orders-summary').innerText());
      const sheet = await page.locator('#orders-table [data-earnings="AAPL"]').evaluateAll((n) => n.map((x) => x.textContent));
      eq(`${where}: the tickets sheet carries the same sentence under its orders`, sheet, ['AAPL: ' + row.sentence]);
      const sheetItems = await page.locator('#orders-table [data-current-reports="AAPL"]').evaluateAll((n) => n.map((x) => x.textContent));
      eq(`${where}: and the items sentence beside it`, sheetItems, ['AAPL: ' + row.items.sentence]);
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('.ss-decision [data-item="risk"]').screenshot({ path: path.join(shotsDir, `earnings-risk-${width}-${theme}.png`) }); }
      // a stock with no ticket has no earnings line: the warning is for orders
      await page.evaluate(() => { location.hash = '#/explore/bursts/AMD'; });
      await page.waitForFunction(() => /AMD/.test((document.querySelector('.ss-detail h2, #detail h2, [data-detail-ticker]') || document.body).textContent));
      await page.waitForTimeout(150);
      const amd = await riskOf(page);
      check(`${where}: AMD's risk item names no earnings date`, !/Earnings/.test(amd), amd);
      check(`${where}: and no current report`, !/current report/i.test(amd), amd);
      await page.evaluate(() => { location.hash = '#/method'; });
      await page.waitForTimeout(250);
      const method = await methodOf(page);
      check(`${where}: Method prints the block's own sentence`, method.includes(full.run.earnings.sentence), full.run.earnings.sentence);
      check(`${where}: which counts the tickets by their current reports`, /SEC current reports \(8-K\)[^.]*1 with a material item/.test(full.run.earnings.sentence), full.run.earnings.sentence);
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      const body = await page.locator('body').innerText();
      check(`${where}: nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      eq(`${where}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- an unknown row is printed as unknown, with its reason: COIL, a ticket on
  // the degraded night, is not in the SEC double's mapping
  {
    const coil = degraded.run.earnings.rows.find((r) => r.ticker === 'COIL');
    check('the degraded fixture carries COIL as unknown, not mapped', !!coil && coil.verdict === 'unknown' && coil.reason === 'not_mapped');
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/degraded.json', NOW, 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/explore/setting-up/COIL' });
    try {
      const risk = await riskOf(page);
      check('unknown: the risk item prints the reason, and nothing reads as clear', risk.includes(coil.sentence) && risk.includes('Earnings date not established'), risk);
      check('unknown: its current reports read not checked, with the same reason', coil.items.status === 'not_checked' && risk.includes(coil.items.sentence) && /not checked: SEC.s ticker list does not name this symbol/.test(coil.items.sentence), risk);
      eq('unknown: page errors', [...errors], []);
    } finally { await context.close(); }
  }

  // ---- two tickets in one stage: each prints its own row, never the other's
  {
    const next = JSON.parse(await readFile(path.join(FIXTURES, 'next.json'), 'utf8'));
    const rows = next.run.earnings.rows.filter((r) => r.stage === 'burst');
    const [nvda, coil] = ['NVDA', 'COIL'].map((t) => rows.find((r) => r.ticker === t));
    check('the next fixture carries two burst tickets with different warnings', !!nvda && !!coil && nvda.sentence !== coil.sentence && next.trades.includes('NVDA') && next.trades.includes('COIL'));
    check('NVDA\'s recent reports are listed and none is material', nvda.items.status === 'listed' && /none is a material agreement \(1\.01\)/.test(nvda.items.sentence) && /7\.01 \(Regulation FD Disclosure\)/.test(nvda.items.sentence), nvda.items.sentence);
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/next.json', '2026-09-11T22:31:00Z', 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/explore/bursts/COIL' });
    try {
      const risk = await riskOf(page);
      check('two tickets: COIL\'s risk item prints COIL\'s row', risk.includes(coil.sentence), risk);
      check('two tickets: and not NVDA\'s', !risk.includes(nvda.sentence), risk);
      check('two tickets: COIL\'s items and not NVDA\'s', risk.includes(coil.items.sentence) && !risk.includes(nvda.items.sentence), risk);
      await page.evaluate(() => { location.hash = '#/explore/bursts/NVDA'; });
      await page.waitForFunction(() => /NVDA/.test((document.querySelector('.ss-detail h2, #detail h2, [data-detail-ticker]') || document.body).textContent));
      await page.waitForTimeout(150);
      const nvdaRisk = await riskOf(page);
      check('two tickets: NVDA\'s risk item prints its listed items', nvdaRisk.includes(nvda.items.sentence) && !nvdaRisk.includes(coil.items.sentence), nvdaRisk);
      for (const r of [nvda, coil]) {
        const sheet = await page.locator(`#orders-table [data-earnings="${r.ticker}"]`).evaluateAll((n) => n.map((x) => x.textContent));
        eq(`two tickets: the sheet gives ${r.ticker} its own sentence`, sheet, [`${r.ticker}: ${r.sentence}`]);
      }
      eq('two tickets: page errors', [...errors], []);
    } finally { await context.close(); }
  }

  // ---- shapes the generator never writes, served under the page's own file
  const cases = [
    ['before', (d) => { delete d.run.earnings; delete d.rules.earnings_risk; }, BEFORE, 'this record predates the earnings warning'],
    ['row', (d) => { d.run.earnings.rows[0].verdict = 'clear'; d.run.earnings.rows[0].sentence = 'No earnings risk.'; }, UNREAD, null],
    ['block', (d) => { d.run.earnings = 'x'; }, UNREAD, 'in a shape this page cannot read'],
    ['rows', (d) => { d.run.earnings.rows = { AAPL: row }; }, UNREAD, null],
    // a row with a verdict the page knows and no sentence is still unreadable, never silence
    ['sentence', (d) => { d.run.earnings.rows.find((r) => r.ticker === 'AAPL').sentence = ''; }, UNREAD, null],
  ];
  for (const [name, mutate, words, methodWords] of cases) {
    const record = clone(full); mutate(record);
    const r = routed(name, record);
    const { page, context, errors } = await open(browser, base, r.url, NOW, 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/explore/bursts/AAPL', beforeLoad: r.beforeLoad });
    try {
      const risk = await riskOf(page);
      check(`${name}: the risk item says the date was not checked or not established`, risk.includes(words), risk);
      check(`${name}: and never prints a forged or absent row as clear`, !risk.includes('No earnings risk') && !risk.includes(row.sentence), risk);
      const sheet = await page.locator('#orders-table [data-earnings="AAPL"]').evaluateAll((n) => n.map((x) => x.textContent));
      eq(`${name}: the sheet says the same`, sheet, ['AAPL: ' + words + ' Check the company’s announcement before entry.']);
      if (methodWords) {
        await page.evaluate(() => { location.hash = '#/method'; });
        await page.waitForTimeout(250);
        const method = await methodOf(page);
        check(`${name}: Method says so in its own words`, method.includes(methodWords), method.slice(0, 200));
      }
      const body = await page.locator('body').innerText();
      check(`${name}: nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      eq(`${name}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- the current-report items under shapes the generator never writes: a
  // version-1 record (every publication from 2 to 6 November 2026) says the
  // check predates it; a row whose items the page cannot read is never no item
  const itemCases = [
    ['v1', (d) => {
      d.run.earnings.version = 1; delete d.run.earnings.items_counts;
      d.run.earnings.rows.forEach((r) => { delete r.items; delete r.current_reports; delete r.current_report_count; });
      d.rules.earnings_risk.version = 1;
      d.run.earnings.sentence = d.run.earnings.sentence.split(' SEC current reports')[0];
    }, ITEMS_V1],
    ['items-missing', (d) => { delete d.run.earnings.rows.find((r) => r.ticker === 'AAPL').items; }, ITEMS_UNREAD],
    ['items-blank', (d) => { d.run.earnings.rows.find((r) => r.ticker === 'AAPL').items.sentence = ''; }, ITEMS_UNREAD],
    ['items-string', (d) => { d.run.earnings.rows.find((r) => r.ticker === 'AAPL').items = 'none'; }, ITEMS_UNREAD],
  ];
  for (const [name, mutate, words] of itemCases) {
    const record = clone(full); mutate(record);
    const r = routed('items-' + name, record);
    const { page, context, errors } = await open(browser, base, r.url, NOW, 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/explore/bursts/AAPL', beforeLoad: r.beforeLoad });
    try {
      const risk = await riskOf(page);
      check(`${name}: the risk item still prints the earnings sentence`, risk.includes(row.sentence), risk);
      check(`${name}: and says the current reports were not checked or not established`, risk.includes(words), risk);
      check(`${name}: and never the fixture's items sentence`, !risk.includes(row.items.sentence), risk);
      const sheet = await page.locator('#orders-table [data-current-reports="AAPL"]').evaluateAll((n) => n.map((x) => x.textContent));
      eq(`${name}: the sheet says the same`, sheet, ['AAPL: ' + words]);
      const body = await page.locator('body').innerText();
      check(`${name}: nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      eq(`${name}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }
}
