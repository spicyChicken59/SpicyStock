/* Cash arithmetic never changes a published ticket. The positive UI control is
   produced by run_evening at $2,000 with a fresh synthetic ledger. */
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const DIR = 'tests/fixtures/cash-preview';
const NOW = '2026-09-11T13:35:00Z';

export async function checkCashPreview({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- cash preview: exact cents, immutable ticket and private single-plan arithmetic');
  const raw = await readFile(path.join(ROOT, DIR, 'publication.json'), 'utf8'), publication = JSON.parse(raw);
  const observed = await readFile(path.join(ROOT, DIR, 'observed.json'), 'utf8');
  const halted = await readFile(path.join(ROOT, DIR, 'halted.json'), 'utf8');
  const corporate = await readFile(path.join(ROOT, DIR, 'corporate-excluded.json'), 'utf8');
  const state = page => page.locator('[data-cash-preview]').getAttribute('data-preview-state');
  const output = page => page.locator('[data-cash-preview-result]').evaluate(node => Object.fromEntries([...node.children].map(item => [item.querySelector('dt').textContent, item.querySelector('dd').textContent])));
  const wait = page => page.waitForFunction(() => ['loaded', 'unavailable', 'practice'].includes(SCStock.observations.facts().state));
  const fill = async (page, cash, fees = '0', quantity = '') => {
    await page.locator('#morning-cash').fill(cash);
    await page.locator('#morning-preview-fees').fill(fees);
    await page.locator('#morning-preview-quantity').fill(quantity);
  };
  for (const [width, theme] of [[1280, 'dark'], [1280, 'light'], [390, 'dark'], [390, 'light'], [721, 'dark'], [721, 'light']]) {
    let sidecar = observed;
    const requests = [];
    const { page, context, errors } = await open(browser, base, '/' + DIR + '/publication.json', NOW, width, {
      theme, hash: '#/explore/setting-up/COIL', reducedMotion: 'reduce', beforeLoad: async page => {
        page.on('request', request => requests.push({ url: request.url(), body: request.postData() }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: sidecar }));
      }
    });
    try {
      await wait(page);
      eq('positive control has producer-sized COIL order', await page.evaluate(() => {
        const c = SCStock.model.stages['setting-up'].find(c => c.ticker === 'COIL');
        return [SCStock.data.account.equity, c.status, c.plan.order_json.quantity, c.plan.order_json.limit_price];
      }), [2000, 'ticket', 4, 111.72]);
      await page.locator('#morning-open').click();
      await page.locator('.ss-morning__prep > summary').click();
      eq('cash starts unknown', await state(page), 'needs_cash');
      eq('fees start unknown', await page.locator('#morning-preview-fees').inputValue(), '');
      await page.locator('#morning-cash').fill('2000');
      eq('blank fees never mean zero', await state(page), 'needs_fees');
      const before = await page.evaluate(() => ({ record: JSON.stringify(SCStock.data), storage: JSON.stringify(localStorage), copies: [...document.querySelectorAll('[data-copy]')].map(n => n.getAttribute('data-copy')) }));
      const requestCount = requests.length;
      await fill(page, '447.88', '1');
      eq('four-share principal/fees/risk are exact', await output(page), {
        'Published shares': '4', 'Your preview shares': '4', 'Buy trigger / limit': '$110.61 / $111.72', 'Protective stop': '$109.50',
        'Principal at the limit': '$446.88', 'Fees buffer': '$1.00', 'Total cash for this preview': '$447.88',
        'Planned price-to-stop risk': '$8.88', 'Cash left after this preview only': '$0.00'
      });
      await fill(page, '447.87', '1');
      eq('one cent below fees-inclusive boundary buys only three', (await output(page))['Your preview shares'], '3');
      await fill(page, '2000', '0', '2');
      eq('owner may choose a smaller whole quantity', [(await output(page))['Your preview shares'], (await output(page))['Principal at the limit']], ['2', '$223.44']);
      await fill(page, '2000', '0', '5');
      eq('cannot exceed published shares even with ample cash', await state(page), 'invalid_quantity');
      await fill(page, '111.71');
      eq('less than one share remains unfunded', await state(page), 'unfunded');
      await fill(page, '111.72');
      eq('exact one-share boundary fits', (await output(page))['Your preview shares'], '1');
      await fill(page, '111.72', '0.01');
      eq('one cent fee can make one share unfunded', await state(page), 'unfunded');
      for (const [field, value, expected] of [['cash', '12.001', 'invalid_cash'], ['cash', '90071992547409.92', 'invalid_cash'], ['fees', '-1', 'invalid_fees'], ['fees', '0.001', 'invalid_fees'], ['quantity', '1.5', 'invalid_quantity'], ['quantity', '0', 'invalid_quantity']]) {
        await fill(page, '2000');
        await page.locator(field === 'cash' ? '#morning-cash' : '#morning-preview-' + field).fill(value);
        eq(field + ' refuses ' + value, await state(page), expected);
        eq('invalid input clears prior result', await page.locator('[data-cash-preview-result] dd').count(), 0);
      }
      await fill(page, '90071992547409.91', '0');
      eq('largest accepted cents display exactly', (await output(page))['Cash left after this preview only'], '$90,071,992,546,963.03');
      check('settled-cash display uses the same exact parser', (await page.locator('[data-morning="cash-status"]').textContent()).startsWith('$90,071,992,547,409.91'));
      await fill(page, '446.88');
      eq('calculator leaves record, saved private data and published copy unchanged', await page.evaluate(() => ({ record: JSON.stringify(SCStock.data), storage: JSON.stringify(localStorage), copies: [...document.querySelectorAll('[data-copy]')].map(n => n.getAttribute('data-copy')) })), before);
      eq('cash edits make no requests', requests.length, requestCount);
      eq('preview contains no executable copy/submit controls', await page.locator('[data-cash-preview] [data-copy], [data-cash-preview] [data-order], [data-cash-preview] button:not([data-handoff-prepare])').count(), 0);
      check('independent cash and original quantity are explicit', (await page.locator('[data-cash-preview]').textContent()).includes('it reserves nothing') && (await page.locator('[data-cash-preview-copy-note]').textContent()).includes('published 4 shares'));
      check(`${width}/${theme}: preview fits dialog and document`, await page.locator('#morning-desk').evaluate(n => n.scrollWidth <= n.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('[data-cash-preview]').scrollIntoViewIfNeeded();
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `cash-preview-${width}-${theme}.png`) });
      }
      await page.locator('#morning-preview-quantity').fill('2');
      await page.locator('#morning-preview-quantity').focus();
      await page.evaluate(() => SCStock.observations.clock(new Date('2026-09-11T13:36:01Z')));
      eq('quote expiry preserves independent calculation draft/focus', await page.locator('#morning-preview-quantity').evaluate(n => [n.value, document.activeElement === n]), ['2', true]);
      eq('dated quote cannot create strategy price gating', await state(page), 'calculated');
      for (const [label, body] of [['halt', halted], ['corporate exclusion', corporate]]) {
        sidecar = body;
        await page.evaluate(() => SCStock.observations.reload()); await wait(page);
        eq(label + ' withdraws cash calculation', await state(page), 'unavailable');
        eq(label + ' leaves no personal result', await page.locator('[data-cash-preview-result] dd').count(), 0);
        check(label + ' is explained beside preview', /halt|corporate|event|acquisition/i.test(await page.locator('[data-cash-preview-status]').textContent()));
      }
      eq('cash preview browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  // One separate tab exercises boundaries without retaining event exclusions.
  const tab = await open(browser, base, '/' + DIR + '/publication.json', NOW, 1280, { beforeLoad: page => page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: observed })) });
  const { page, context } = tab;
  try {
    await wait(page); await page.locator('#morning-open').click(); await page.locator('.ss-morning__prep > summary').click();
    const pure = await page.evaluate(() => {
      // Explicit synthetic arithmetic only. These numbers are not a live ZIM
      // recommendation, nor an override of any corporate-event exclusion.
      const order = { symbol: 'SYNTHETIC', action: 'buy', quantity: 2, order_type: 'stop_limit', stop_price: 30.38, limit_price: 30.68, time_in_force: 'day', conditional: 'one_triggers_the_other', then: { action: 'sell', quantity: 2, order_type: 'stop', stop_price: 29.66, time_in_force: 'gtc' } };
      const calc = (cash, fees = '0', patch = {}) => SCStock.cashPreview.calculate({ cash, fees, order: { ...order, ...patch } });
      return { thresholds: ['30.67', '30.68', '61.35', '61.36', '2000'].map(cash => calc(cash).quantity), fee: calc('61.36', '0.01').quantity,
        equal: calc('100', '0', { stop_price: 30.68 }).quantity,
        malformed: [calc('100', '0', { stop_price: 29.65 }), calc('100', '0', { stop_price: 31 }), calc('100', '0', { limit_price: 30.681 }), calc('100', '0', { quantity: 3 }), calc('100', '0', { time_in_force: 'gtc' }), calc('100', '0', { action: 'sell' })].map(r => r.state),
        cents: ['', '0', '0.01', '90071992547409.91', '90071992547409.92', '00000000000000000000000', '1e3'].map(s => SCStock.cashPreview.cents(s) ?? null) };
    });
    eq('synthetic two-share cent thresholds', pure.thresholds, [null, 1, 1, 2, 2]);
    eq('fees consume cash before quantity division', pure.fee, 1);
    eq('backend-supported equal trigger and limit accepted', pure.equal, 2);
    eq('malformed protective/order geometry refused', pure.malformed, Array(6).fill('invalid_order'));
    eq('safe exact parser boundaries and unknowns', pure.cents, [null, 0, 1, 9007199254740991, null, null, null]);
    const render = (record, now = NOW) => page.evaluate(({ record, now }) => SCStock.render(record, new Date(now)), { record, now });
    for (const [label, change, now] of [
      ['fixture', record => { record.fixture = { label: 'Explicit synthetic refusal control' }; }],
      ['account mismatch', record => { record.account.equity = 10000; }],
      ['model slot mismatch', record => { record.account.max_open_positions = 5; }],
      ['no ticket', record => { record.trades = []; record.watchlist.top = []; }],
      ['withheld', record => { const p = record.watchlist.top.find(r => r.ticker === 'COIL').plan; p.action = 'refused'; p.eligible = false; p.order_json = null; }],
      ['symbol mismatch', record => { record.watchlist.top.find(r => r.ticker === 'COIL').plan.order_json.symbol = 'WRONG'; }],
      ['plan/order quantity mismatch', record => { record.watchlist.top.find(r => r.ticker === 'COIL').plan.shares = 3; }],
      ['plan/order level mismatch', record => { record.watchlist.top.find(r => r.ticker === 'COIL').plan.stop += 0.01; }],
      ['expired', () => {}, '2026-09-11T14:00:00Z'],
      ['stale', () => {}, '2026-09-16T13:35:00Z']
    ]) {
      const record = structuredClone(publication); change(record); await render(record, now || NOW);
      // Finish binding even when the old sidecar no longer matches these
      // explicit malformed controls. Pending binding must not mask this gate.
      await page.evaluate(raw => SCStock.observations.bind(SCStock.data, raw), JSON.stringify(record)); await wait(page);
      await fill(page, '2000');
      eq(label + ' cannot show personal quantity', await state(page), 'unavailable');
      eq(label + ' removes prior amounts', await page.locator('[data-cash-preview-result] dd').count(), 0);
    }
    await render(publication); await fill(page, '2000');
    eq('unbound current record initially awaits observation binding', await state(page), 'unavailable');
    await page.evaluate(raw => SCStock.observations.bind(SCStock.data, raw), raw); await wait(page);
    await fill(page, '447.88', '1', '2');
    const revision = structuredClone(publication), plan = revision.watchlist.top.find(r => r.ticker === 'COIL').plan;
    // Explicit malformed/publication-boundary control: new order quantities
    // cannot inherit the previous order's fees or chosen quantity.
    plan.order_json.quantity = 3; plan.order_json.then.quantity = 3;
    await render(revision);
    eq('same-session revision keeps cash but clears plan-specific drafts', await page.evaluate(() => ['morning-cash', 'morning-preview-fees', 'morning-preview-quantity'].map(id => document.getElementById(id).value)), ['447.88', '', '']);
    eq('unbound revised order does not keep old result', await state(page), 'unavailable');
    await page.evaluate(({ record }) => {
      window.CashRealDate = Date; window.cashClock = '2026-09-11T13:59:59Z';
      window.Date = class extends CashRealDate { constructor(...a) { super(...(a.length ? a : [window.cashClock])); } static now() { return new CashRealDate(window.cashClock).getTime(); } };
      SCStock.render(record);
    }, { record: publication });
    await page.evaluate(raw => SCStock.observations.bind(SCStock.data, raw), raw); await wait(page); await fill(page, '447.88', '1');
    eq('before deadline calculation remains available', await state(page), 'calculated');
    await page.evaluate(() => { window.cashClock = '2026-09-11T14:00:00Z'; });
    await page.locator('#morning-preview-quantity').fill('2');
    eq('input at exact cutoff checks clock immediately', await state(page), 'unavailable');
    eq('deadline preserves focused draft while withdrawing calculation', await page.locator('#morning-preview-quantity').evaluate(n => [n.value, document.activeElement === n]), ['2', true]);
    await page.evaluate(() => { window.Date = CashRealDate; });
    await page.reload(); await page.waitForFunction(() => document.documentElement.hasAttribute('data-ss-rendered')); await wait(page);
    eq('reload clears all unverified personal inputs', await page.evaluate(() => ['morning-cash', 'morning-preview-fees', 'morning-preview-quantity'].map(id => document.getElementById(id).value)), ['', '', '']);
    eq('cash boundary browser errors', [...tab.errors], []);
  } finally { await context.close(); }

  const multipleReceipt = await readFile(path.join(ROOT, DIR, 'observed-multiple.json'), 'utf8');
  const multiple = await open(browser, base, '/' + DIR + '/publication-multiple.json', NOW, 390, {
    beforeLoad: page => page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: multipleReceipt }))
  });
  try {
    const page = multiple.page; await wait(page);
    await page.locator('#morning-open').click(); await page.locator('.ss-morning__prep > summary').click();
    eq('multiple-plan control is a genuine combined producer allocation', await page.evaluate(() => [SCStock.data.cash_budget.committed_usd, ...SCStock.morning.facts(SCStock.data, SCStock.avail, SCStock.model).tickets.map(c => c.ticker)]), [510.1, 'AAPL', 'COIL']);
    await page.locator('#morning-preview-plan').selectOption('setting-up:COIL'); await fill(page, '447.88', '1', '4');
    const first = await output(page);
    eq('first independent plan fits exactly', [first['Your preview shares'], first['Cash left after this preview only']], ['4', '$0.00']);
    await page.locator('#morning-preview-plan').selectOption('bursts:AAPL');
    eq('switching plan keeps entered cash but clears its fee/quantity estimates', await page.evaluate(() => ['morning-cash', 'morning-preview-fees', 'morning-preview-quantity'].map(id => document.getElementById(id).value)), ['447.88', '', '']);
    await page.locator('#morning-preview-fees').fill('1');
    eq('second plan is its own calculation, not a reserved basket', [(await output(page))['Your preview shares'], (await output(page))['Total cash for this preview']], ['1', '$64.22']);
    await page.locator('#morning-preview-plan').selectOption('setting-up:COIL'); await page.locator('#morning-preview-fees').fill('1');
    eq('returning to first plan never implies second plan consumed/reserved cash', await output(page), first);
    check('no combined affordability claim accompanies independent results', (await page.locator('[data-cash-preview]').textContent()).includes('Each calculation uses the cash you entered independently; it reserves nothing'));
    eq('multiple-plan browser errors', [...multiple.errors], []);
  } finally { await multiple.context.close(); }
}
