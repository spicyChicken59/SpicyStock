/* Morning preparation with synthetic published records. The module cannot
   turn a setup into a ticket or send a cash/checklist entry anywhere. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-11T13:20:00Z';

export async function checkMorning({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- morning desk: Chicago time, account reference and immutable plans');
  const control = structuredClone(data);
  delete control.fixture; // Explicit synthetic control for real-publication UI states.
  const matching = structuredClone(control);
  matching.account = { ...matching.account, equity: 2000, risk_pct: 0.5, max_position_pct: 25 };
  const next = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/next.json')));
  const render = (page, record, now = NOW) => page.evaluate(({ record, now }) => SCStock.render(record, new Date(now)), { record, now });
  const text = (page, key) => page.locator('#morning-desk [data-morning="' + key + '"]').textContent();

  for (const width of [1280, 390]) for (const theme of ['dark', 'light']) {
    const { page, context, errors } = await open(browser, base, '/morning-control.json', NOW, width, {
      theme, reducedMotion: 'reduce', beforeLoad: async page => {
        await page.route('**/morning-control.json', route => route.fulfill({ json: control }));
        await page.route('https://api.github.com/**', route => route.abort());
      }
    });
    try {
      eq('morning desk starts closed for scanning', await page.locator('#morning-desk').evaluate(node => node.open), false);
      check('Chicago window is named on morning control', (await page.locator('#morning-open').getAttribute('title')).includes('8:30 AM–9:00 AM CT'));
      await page.locator('#morning-open').focus(); await page.keyboard.press('Enter');
      eq('keyboard opens the morning dialog', await page.locator('#morning-desk').evaluate(node => node.open), true);
      const before = await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), storage: JSON.stringify(localStorage) }));
      const ticketCounts = await page.evaluate(() => Object.values(SCStock.model.stages).map(rows => rows.filter(row => row.status === 'ticket').length));
      eq(`${width} ${theme}: both ticket families counted`, await text(page, 'plans'), ticketCounts[0] + ' burst · ' + ticketCounts[1] + ' setting up');
      check('Chicago window uses the recorded instants', (await text(page, 'window')).includes('8:30 AM–9:00 AM CT'));
      check('Chicago preparation uses the recorded instant', (await text(page, 'phase')).includes('8:28 AM CT'));
      check('Chicago conversion also follows winter offsets', await page.evaluate(() => {
        const av = { ...SCStock.avail, timing: { ...SCStock.avail.timing, known: true,
          opens: new Date('2026-11-27T09:30:00-05:00'), cutoff: new Date('2026-11-27T10:00:00-05:00'), prepareBy: new Date('2026-11-27T09:28:00-05:00') } };
        const facts = SCStock.morning.facts(SCStock.data, av, SCStock.model);
        return facts.window.includes('8:30 AM–9:00 AM CT') && facts.prepare.includes('8:28 AM CT');
      }));
      eq('account mismatch is prominent', await text(page, 'headline'), 'Account sizing needs an update');
      check('published 10k quantity is explicitly incompatible', (await text(page, 'sizing')).includes('$10,000') && (await text(page, 'sizing')).includes('Do not copy these quantities'));
      check('reference is the 2k cash account and bounded baseline', (await page.locator('.ss-morning__reference').textContent()).includes('$2,000 cash-account reference · $10 planned risk (0.5%) · $500 position cap (25%)'));
      eq('settled cash is unknown initially', await page.locator('#morning-cash').inputValue(), '');
      check('unknown cash is visible while checklist is closed', (await text(page, 'cash')).includes('unknown'));
      await page.locator('.ss-morning__prep summary').focus();
      await page.keyboard.press('Enter');
      eq('manual prep opens with keyboard', await page.locator('.ss-morning__prep').evaluate(n => n.open), true);
      await page.locator('#morning-cash').fill('1250.25');
      check('cash remains explicitly user-entered and unverified', (await text(page, 'cash')).includes('$1,250.25 settled cash entered by you; not verified'));
      await page.locator('[data-morning-check="quote"]').check();
      await render(page, control);
      eq('same-session render preserves cash', await page.locator('#morning-cash').inputValue(), '1250.25');
      eq('same-publication render preserves manual reminder', await page.locator('[data-morning-check="quote"]').isChecked(), true);
      eq('render preserves open disclosure', await page.locator('.ss-morning__prep').evaluate(n => n.open), true);
      eq('cash changes neither record nor local storage', await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), storage: JSON.stringify(localStorage) })), before);
      await page.locator('#morning-cash').fill('0');
      check('zero does not imply purchase funding', (await text(page, 'cash')).includes('no new cash purchase is funded'));
      for (const invalid of ['-1', '1e3', '12.001', 'Infinity', '<img src=x>']) {
        await page.locator('#morning-cash').fill(invalid);
        eq('invalid cash rejected: ' + invalid, await page.locator('#morning-cash').getAttribute('aria-invalid'), 'true');
      }
      await page.locator('#morning-cash').fill('1000');
      eq('valid cash clears validation', await page.locator('#morning-cash').getAttribute('aria-invalid'), 'false');
      eq('manual checks cannot add executable orders', await page.locator('#morning-desk [data-copy], #morning-desk [data-order]').count(), 0);
      check(`${width} ${theme}: preparation fits viewport`, await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `morning-${width}-${theme}.png`) });
      }
      const revision = structuredClone(control);
      revision.run.published_at = '2026-09-10T22:45:00Z';
      await render(page, revision);
      eq('revised publication clears broker acknowledgements', await page.locator('[data-morning-check="quote"]').isChecked(), false);
      eq('same-session revised publication keeps cash entry', await page.locator('#morning-cash').inputValue(), '1000');
      await render(page, next, '2026-09-11T22:31:00Z');
      eq('new trading session clears cash', await page.locator('#morning-cash').inputValue(), '');
      await render(page, matching);
      eq('matching reference resolves sizing warning', await page.locator('#morning-desk').getAttribute('data-sizing-match'), 'true');
      check('matching reference never verifies actual funds', (await text(page, 'sizing')).includes('balances and holdings are still unverified'));
      await page.locator('#morning-cash').fill('1500');
      await page.reload();
      await page.waitForFunction(() => document.documentElement.hasAttribute('data-ss-rendered'));
      await page.locator('#morning-open').click();
      eq('reload clears local cash', await page.locator('#morning-cash').inputValue(), '');

      for (const [name, record, now, expected] of [
        ['demo', data, NOW, 'Practice record — no live entries'],
        ['expired', matching, '2026-09-11T14:00:00Z', 'No entries to place from this record'],
        ['stale', matching, '2026-09-16T13:40:00Z', 'No entries to place from this record'],
        ['missing timing', { ...matching, run: { ...matching.run, timing: null } }, NOW, 'No entries to place from this record'],
        ['RED', { ...matching, breadth: { ...matching.breadth, regime: { ...matching.breadth.regime, verdict: 'red', size_multiplier: 0 } } }, NOW, 'Stand aside for new longs'],
        ['unknown market', { ...matching, breadth: {} }, NOW, 'Market permission is unavailable']
      ]) {
        await render(page, record, now);
        eq(name + ': no live-entry suggestion', await text(page, 'headline'), expected);
        eq(name + ': no available marker', await page.locator('#morning-desk').getAttribute('data-morning-offered'), 'false');
        check(name + ': recorded plans are inspection only', (await text(page, 'plans')).includes('inspect only'));
      }
      const noPlans = structuredClone(matching);
      noPlans.trades = []; noPlans.watchlist = { top: [], also_quiet: [] };
      await render(page, noPlans);
      eq('zero plans have a plain headline', await text(page, 'headline'), 'No qualifying entry plans');
      await page.evaluate(() => SCStock.navigate('#/market'));
      await page.locator('[data-morning="next"]').click();
      await page.waitForFunction(() => !document.getElementById('view-explore').hidden && document.querySelector('#decision-gates details').open);
      eq('no-plan action opens existing gate explanation', await page.locator('#decision-gates details').evaluate(node => node.open), true);
      eq('no-plan action returns to the scan from another view', await page.locator('#view-explore').isVisible(), true);
      eq('research action closes morning dialog', await page.locator('#morning-desk').evaluate(node => node.open), false);
      await render(page, matching);
      await page.evaluate(() => SCStock.navigate('#/market'));
      await page.locator('#morning-open').click();
      await page.locator('[data-morning="next"]').click();
      await page.waitForFunction(() => document.activeElement.id === 'detail');
      eq('recorded-plan action returns to selected research with focus', await page.locator('#view-explore').isVisible(), true);
      await page.locator('#morning-open').click();

      // The live clock must withdraw preparation at the exact cutoff without
      // replacing the cash input, losing focus or clearing half-typed content.
      await page.evaluate(record => {
        window.MorningRealDate = Date;
        window.morningClockAt = '2026-09-11T13:59:59Z';
        window.Date = class extends MorningRealDate {
          constructor(...args) { super(...(args.length ? args : [window.morningClockAt])); }
          static now() { return new MorningRealDate(window.morningClockAt).getTime(); }
        };
        SCStock.render(record);
      }, matching);
      await page.locator('.ss-morning__prep').evaluate(node => { node.open = true; });
      await page.locator('#morning-cash').fill('125.');
      await page.locator('#morning-cash').focus();
      await page.evaluate(() => { window.morningClockAt = '2026-09-11T14:00:00Z'; SCStock.reclock(); });
      eq('clock cutoff withdraws morning entry availability', await page.locator('#morning-desk').getAttribute('data-morning-offered'), 'false');
      eq('clock preserves cash draft and focus', await page.locator('#morning-cash').evaluate(node => [node.value, document.activeElement === node]), ['125.', true]);
      await page.evaluate(() => { window.Date = MorningRealDate; });
      await page.keyboard.press('Escape');
      eq('Escape closes morning desk and restores opener focus', await page.evaluate(() => [document.getElementById('morning-desk').open, document.activeElement.id]), [false, 'morning-open']);
      const eventRecord = structuredClone(matching), row = eventRecord.bursts.find(b => b.plan && b.plan.order_json);
      if (row) {
        eventRecord.trades = eventRecord.trades.filter(ticker => ticker !== row.ticker);
        row.plan.eligible = false; row.plan.action = 'refused'; row.plan.order_json = null; row.plan.order_line = null;
        row.plan.reason = 'Known cash-acquisition event: cash deal pending.';
        row.plan.event_risk = { version: 1, blocked: true, reason: row.plan.reason, registry_reviewed_on: '2026-09-10', matches: [{
          issuer: 'Synthetic event issuer', evidence_as_of: '2026-09-09', review_due: '2026-09-12', review_overdue: false,
          sources: [ { title: 'Issuer transaction announcement', published_on: '2026-09-09', url: 'https://example.com/transaction', quote: 'Acquisition for cash <img src=x>.' },
            { title: 'Unsafe link remains text', published_on: '2026-09-09', url: 'javascript:alert(1)' } ]
        }] };
        await render(page, eventRecord);
        await page.evaluate(ticker => SCStock.navigate('#/explore/bursts/' + ticker), row.ticker);
        check('known corporate event is the principal risk', (await page.locator('#detail [data-item="risk"]').textContent()).includes('Recorded corporate event: Known cash-acquisition event'));
        await page.locator('[data-event-sources] summary').click();
        eq('event evidence links only a safe source URL', await page.locator('[data-event-sources] a').evaluateAll(nodes => nodes.map(node => node.href)), ['https://example.com/transaction']);
        check('event source timing and limited coverage are explicit', (await page.locator('[data-event-sources]').textContent()).includes('2026-09-09') && (await page.locator('[data-event-sources]').textContent()).includes('not a live or complete news screen'));
        eq('source quote stays text, never markup', await page.locator('[data-event-sources] img').count(), 0);
        eq('event-refused candidate has no copy action', await page.locator('#detail [data-copy]').count(), 0);
      } else check('corporate-event UI control has a published plan to exercise', false);
      eq('morning browser errors', [...errors], []);
    } finally { await context.close(); }
  }
}
