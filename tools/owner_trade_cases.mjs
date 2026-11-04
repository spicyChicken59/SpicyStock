/* The owner's own trade on a listed name without a ticket (#110, 4 November
   2026): the detail's "Record a trade I made on this name" opens a blank private
   record bound to the publication's row, its reported fill and stop stay
   browser-local, and the model exit reference is arithmetic from the record's
   own archived rules. Every broker fact here is SYNTHETIC; no broker, provider
   or real trade is involved, and nothing here is anyone's result. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const SOURCE = 'tests/fixtures/cash-preview';
const KEY = 'spicystock:handoff:v1';
// 10:05 AM New York on the publication's applicable session, 2026-09-11: a
// fill reported at 9:41 is in the past, a save is not refused as future.
const START = '2026-09-11T14:05:00.000Z';
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const facts = (page, selector) => page.locator(selector).evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const records = page => page.evaluate(() => SCStock.handoff.list());
const rawStore = page => page.evaluate(key => localStorage.getItem(key), KEY);
const sha = raw => createHash('sha256').update(raw).digest('hex');

export async function checkOwnerTrades({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- owner trades: a listed name without a ticket, the record\'s row frozen, the fill and stop private, the model exits a reference');
  const publicationBytes = await readFile(path.join(ROOT, SOURCE, 'publication-multiple.json'));
  const publication = JSON.parse(publicationBytes.toString('utf8')), publicationSha = sha(publicationBytes);
  const backup = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/first-trade/backup.json'), 'utf8'));
  const run = async (name, fn) => { try { await fn(); } catch (error) { check(name + ': workflow completes', false, error.stack); } };
  const launch = async ({ width = 1280, data = '/' + SOURCE + '/publication-multiple.json', hash = '#/explore/bursts/NVDA', seed = null, start = START, bound = true } = {}) => {
    const requests = [];
    const tab = await open(browser, base, data, null, width, {
      theme: width === 390 ? 'light' : 'dark', hash, lens: 'all', reducedMotion: 'reduce', beforeLoad: async (page, context) => {
        page.setDefaultTimeout(8000);
        await context.addInitScript(({ start, seed, key }) => {
          const Native = Date; window.__ownerClock = Native.parse(start);
          window.Date = class extends Native { constructor(...args) { super(...(args.length ? args : [window.__ownerClock])); } static now() { return window.__ownerClock; } };
          if (seed !== null) localStorage.setItem(key, seed);
          const put = Storage.prototype.setItem; window.__ownerWrites = 0;
          Storage.prototype.setItem = function (name, raw) { if (name === key) window.__ownerWrites++; return put.call(this, name, raw); };
        }, { start, seed, key: KEY });
        page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
      }
    });
    // a practice record (a page fixture) binds no canonical hash; the real
    // publication does, and the owner control reads it
    if (bound) await tab.page.waitForFunction(() => SCStock.observations && SCStock.observations.facts().canonicalHash && !SCStock.observations.facts().pending);
    return { ...tab, requests };
  };
  const at = async (page, name, iso) => {
    await page.evaluate(iso => { window.__ownerClock = Date.parse(iso); SCStock.reclock(); }, iso);
    eq(name + ': the page reads ' + iso, await page.evaluate(() => SCStock.avail && SCStock.avail.at && new Date(SCStock.avail.at).toISOString()), iso);
  };
  const set = async (page, fields) => { for (const [key, value] of Object.entries(fields)) await field(page, key).fill(value); };
  // Every save, accepted or refused, ends in a message; two refusals in a row
  // can carry the same words, so the message is cleared before the press and
  // the press is complete when the page has written one.
  const save = async page => {
    await page.evaluate(() => { document.querySelector('[data-handoff-message]').textContent = ''; });
    await page.locator('[data-handoff-save]').click();
    await page.waitForFunction(() => document.querySelector('[data-handoff-message]').textContent !== '');
  };
  const capture = async (page, name, selector) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true }); await page.locator(selector).scrollIntoViewIfNeeded();
    await page.locator(selector).screenshot({ path: path.join(shotsDir, name + '.png') });
  };
  const button = (page, ticker) => page.locator('[data-owner-trade="' + ticker + '"]');
  const detail = async (page, stage, ticker) => {
    await page.evaluate(hash => { location.hash = hash; }, '#/explore/' + stage + '/' + ticker);
    await page.waitForFunction(ticker => (document.querySelector('[data-detail-ticker]') || {}).getAttribute && document.querySelector('[data-detail-ticker]').getAttribute('data-detail-ticker') === ticker || (document.querySelector('#detail h2, #detail h3') || {}).textContent?.includes(ticker), ticker).catch(() => {});
  };
  const expectedRules = { sell_half_pct: publication.rules.plan.sell_half_pct, sell_half_day: publication.rules.plan.sell_half_day, final_exit_day: publication.rules.plan.final_exit_day, entry_day: publication.rules.plan.entry_day };
  const fill = { submitted_quantity: '102', filled_quantity: '102', average_price: '70.345', filled_at: '2026-09-11T13:41:00Z', protected_quantity: '102', protection_confirmed_at: '2026-09-11T13:42:00Z', account_label: 'Rollover IRA', stop_price: '67.85' };

  for (const width of [390, 1280]) await run('owner trade/' + width, async () => {
    const tab = await launch({ width }), { page, errors } = tab, name = 'owner trade/' + width;
    try {
      eq(name + ': the publication the page hashed is the fixture', await page.evaluate(() => SCStock.observations.facts().canonicalHash), publicationSha);
      eq(name + ': a listed burst without a ticket offers the owner-trade control', await button(page, 'NVDA').count(), 1);
      await detail(page, 'bursts', 'AAPL');
      eq(name + ': a ticketed name offers no owner-trade control (its draft and report are the ticket\'s)', await button(page, 'AAPL').count(), 0);
      await detail(page, 'bursts', 'TSLA');
      eq(name + ': a withheld setup offers the control', await button(page, 'TSLA').count(), 1);
      await detail(page, 'setting-up', 'COIL');
      eq(name + ': a setting-up ticket offers none', await button(page, 'COIL').count(), 0);
      await detail(page, 'bursts', 'NVDA');
      const candidate = await page.evaluate(() => { const c = SCStock.model.stages.bursts.find(c => c.ticker === 'NVDA'); return { rank: c.rank, grade: c.grade, score: c.score, admitted: c.admitted, status: c.status, reason: c.reason, scan: c.row.scan, evidence: c.row.evidence && c.row.evidence.id }; });
      check(name + ': NVDA carries no ticket in this record', candidate.status !== 'ticket');
      const start = tab.requests.length;
      await button(page, 'NVDA').focus(); await page.keyboard.press('Enter');
      eq(name + ': the Morning desk opens on the blank record', await page.locator('#morning-desk').evaluate(node => node.open), true);
      eq(name + ': the editor is in the owner-unsaved mode', await page.locator('[data-handoff-mode]').first().getAttribute('data-handoff-mode'), 'owner-unsaved');
      eq(name + ': the heading names the stock and that it is unsaved', await page.locator('#handoff-title').textContent(), 'NVDA · unsaved record of your own trade');
      eq(name + ': every field starts blank: no quantity, price, time, account or stop is filled in from the record', await page.locator('[data-handoff-field]').evaluateAll(nodes => nodes.map(node => node.value)), Array(16).fill(''));
      eq(name + ': opening writes nothing', [await rawStore(page), await page.evaluate(() => window.__ownerWrites)], [null, 0]);
      const words = await page.locator('[data-handoff-owner-source]').textContent();
      check(name + ': the source words name the record\'s listing and grant no permission', words.startsWith('Your own trade on NVDA, not a SpicyStock ticket or model fill. The record listed it under Bursts at rank ' + candidate.rank + ', mechanical grade ' + candidate.grade) && words.includes('grants no entry permission'));
      eq(name + ': the account label is the first field group', await page.locator('[data-handoff-field]').first().getAttribute('data-handoff-field'), 'account_label');
      await capture(page, 'owner-blank-' + width, '#morning-desk');
      await save(page); eq(name + ': a blank record cannot be saved', await rawStore(page), null);
      await set(page, { submitted_quantity: '102', filled_quantity: '0' }); await save(page);
      eq(name + ': a zero fill is not an executed trade', await rawStore(page), null);
      await set(page, { ...fill, filled_quantity: '102' }); await save(page);
      const items = await records(page);
      eq(name + ': one owner trade is saved', items.map(item => item.kind), ['owner_trade']);
      const item = items[0];
      if (!item) return;
      eq(name + ': its identity is the publication, the stage and the ticker', item.id, publicationSha + ':owner:bursts:NVDA');
      eq(name + ': the source freezes the row as the page read it', item.source, {
        ticker: 'NVDA', stage: 'bursts', publication: { sha256: publicationSha, session: publication.run.session, published_at: publication.run.published_at, rules_version: publication.app.rules_version },
        row: { rank: candidate.rank, grade: candidate.grade, score: candidate.score, scan: candidate.scan, admitted: candidate.admitted, status: candidate.status, reason: candidate.reason },
        evidence_id: candidate.evidence, rules: expectedRules, schedule: { entry_session: '2026-09-11', sell_half_session: '2026-09-15', final_session: '2026-09-17' } });
      eq(name + ': the fill, the account and the stop are the owner\'s words', [item.report.filled_quantity, item.report.average_price, item.report.account_label, item.report.stop_price], [102, '70.345', 'Rollover IRA', '67.85']);
      eq(name + ': the record is version 4', [item.version, JSON.parse(await rawStore(page)).version], [4, 4]);
      eq(name + ': the editor shows the saved owner trade', await page.locator('[data-handoff-mode]').first().getAttribute('data-handoff-mode'), 'owner_trade');
      const reference = await page.locator('[data-handoff-exit-reference-text]').textContent();
      check(name + ': the sell-half reference is +8% of the reported fill, to the cent', reference.includes('Sell-half reference: $75.97 (+8% of your reported average fill of $70.345'));
      check(name + ': day 3 and day 5 are the record\'s own calendar sessions', reference.includes('places day 3 on 2026-09-15') && reference.includes('day 5 on 2026-09-17') && reference.includes('counted from 2026-09-11 as day 1'));
      check(name + ': the stop is reported, not computed', reference.includes('Your reported protective stop: $67.85.'));
      check(name + ': the reference decides nothing', reference.includes('does not decide whether an exit is due and SpicyStock places and cancels nothing'));
      const shown = await facts(page, '[data-handoff-summary]');
      eq(name + ': the account and stop rows print the owner\'s words', [shown['Broker account (your label)'], shown['Protective stop price reported']], ['Rollover IRA', '$67.85']);
      eq(name + ': no order can be copied and no readback exists', await page.evaluate(id => [SCStock.handoff.copy(id).ok, SCStock.handoff.readback(SCStock.handoff.find(id))], item.id), [false, '']);
      eq(name + ': no warning while the fill is on the record\'s session', await page.evaluate(id => SCStock.handoff.summary(SCStock.handoff.find(id)).warnings, item.id), []);
      await capture(page, 'owner-saved-' + width, '#morning-desk');
      // a fill on another New York day is named, not refused
      await set(page, { filled_at: '2026-09-14T13:41:00Z', protection_confirmed_at: '2026-09-14T13:42:00Z' });
      await at(page, name, '2026-09-14T20:00:00.000Z'); await save(page);
      const warnings = await page.evaluate(id => SCStock.handoff.summary(SCStock.handoff.find(id)).warnings, item.id);
      eq(name + ': a fill on another session than the record counts from is named', warnings, ['Reported fill date 2026-09-14 (New York) is not the session this record’s exit reference counts from, 2026-09-11.']);
      check(name + ': the reference says the dates are the record\'s, not the trade\'s', (await page.locator('[data-handoff-exit-reference-text]').textContent()).includes('Your reported fill falls on 2026-09-14 (New York), not on 2026-09-11'));
      // the exit under the reported stop
      await set(page, { cancelled_quantity: '0', exited_quantity: '102', exited_at: '2026-09-14T14:35:00Z', average_exit_price: '67.10', entry_fees: '0.00', exit_fees: '0.01' }); await save(page);
      const result = await page.evaluate(id => { const s = SCStock.handoff.summary(SCStock.handoff.find(id)); return [s.completed_result.state, s.completed_result.net_display, s.beyond_stop && s.beyond_stop.total_display]; }, item.id);
      eq(name + ': the completed result (102 × (67.10 − 70.345) − $0.01) and the gap past the reported stop', result, ['complete', '-$331.00', '$76.50']);
      const amounts = await facts(page, '[data-handoff-result-amounts]');
      check(name + ': the gap row is measured against the owner\'s reported stop', (amounts['Average exit below your reported stop'] || '').startsWith('$0.75 a share on average · the 102 reported shares exited for $76.50 less than at the stop'));
      // the same name again opens the saved record, never a second one
      // the desk is a modal dialog over the page: close it as its own control does before the detail's button is pressed again
      await page.evaluate(() => { const desk = document.getElementById('morning-desk'); if (desk.open) desk.close(); });
      await detail(page, 'bursts', 'NVDA');
      await button(page, 'NVDA').click();
      eq(name + ': opening again chooses the saved record', [await page.locator('[data-handoff-mode]').first().getAttribute('data-handoff-mode'), (await records(page)).length], ['owner_trade', 1]);
      check(name + ': and says so', (await page.locator('[data-handoff-message]').textContent()).includes('already has a private record'));
      eq(name + ': the backup counts the owner trade apart', await page.evaluate(() => { const b = SCStock.handoff.exportBackup(); return [b.ok, b.summary.owner_count, b.summary.planned_count, b.summary.independent_count, b.summary.version]; }), [true, 1, 0, 0, 4]);
      // every request since the page opened: the record's own loads among them,
      // so the list is never empty and the words are looked for in each
      check(name + ': the page made requests to look through', tab.requests.length > 0);
      eq(name + ': no request carries the owner\'s words', tab.requests.filter(r => /NVDA|Rollover|67\.85|70\.345|\b102\b/.test(r.url + (r.body || ''))), []);
      eq(name + ': nothing is posted', tab.requests.filter(r => r.method !== 'GET'), []);
      eq(name + ': no page error', Array.from(errors), []);
    } finally { await tab.context.close(); }
  });

  await run('a practice record refuses', async () => {
    const tab = await launch({ data: '/tests/fixtures/page/full.json', hash: '#/explore/bursts/TSLA', start: '2026-09-11T14:05:00.000Z', bound: false }), { page } = tab, name = 'practice record';
    try {
      eq(name + ': the control is offered on the withheld name', await button(page, 'TSLA').count(), 1);
      await button(page, 'TSLA').click();
      const status = page.locator('[data-owner-trade-status]').first();
      eq(name + ': the refusal names the practice record', (await status.textContent()).includes('This is a practice record. No trade of yours is recorded against a simulated publication.'), true);
      eq(name + ': the refusal is visible beside the control', await status.evaluate(node => !node.hidden), true);
      eq(name + ': nothing is saved or written', [await rawStore(page), await page.evaluate(() => window.__ownerWrites)], [null, 0]);
    } finally { await tab.context.close(); }
  });

  await run('a version 3 store is read as it is and upgraded only by an explicit save', async () => {
    const seed = JSON.parse(JSON.stringify(backup)); seed.version = 3;
    for (const item of seed.items) { item.version = 3; delete item.report.account_label; delete item.report.stop_price; }
    const seedRaw = JSON.stringify(seed);
    const tab = await launch({ seed: seedRaw }), { page } = tab, name = 'version 3 store';
    try {
      const listed = await records(page);
      eq(name + ': both planned records read, their new fields unknown', listed.map(item => [item.version, item.kind, item.report.account_label, item.report.stop_price]), [[4, 'planned_handoff', null, null], [4, 'planned_handoff', null, null]]);
      eq(name + ': reading writes nothing and leaves the bytes', [await page.evaluate(() => window.__ownerWrites), await rawStore(page)], [0, seedRaw]);
      await button(page, 'NVDA').click();
      await set(page, fill); await save(page);
      const store = JSON.parse(await rawStore(page));
      eq(name + ': the explicit save writes version 4 with every record upgraded', [store.version, store.items.map(item => item.version), store.items.map(item => item.kind)], [4, [4, 4, 4], ['planned_handoff', 'planned_handoff', 'owner_trade']]);
      eq(name + ': the old records keep their facts and gain the two unknown fields', store.items.slice(0, 2).map(item => item.report), seed.items.map(item => ({ ...item.report, account_label: null, stop_price: null })));
    } finally { await tab.context.close(); }
  });

  await run('the desk reference follows the session', async () => {
    const tab = await launch(), { page } = tab, name = 'desk reference';
    try {
      // the publication measured 2026-09-10 at the $2,000 reference of its day
      const sept = await page.evaluate(() => { const f = SCStock.morning.facts(SCStock.data, SCStock.avail, SCStock.model); return [f.reference.equity, f.matched, f.referenceWords]; });
      eq(name + ': a September publication is read against the $2,000 reference', sept, [2000, true, '$2,000 cash-account reference · $10 planned risk (0.5%) · $500 position cap (25%)']);
      const now = await page.evaluate(() => { const data = JSON.parse(JSON.stringify(SCStock.data)); data.run.session = '2026-11-04'; data.account.equity = 30000; const f = SCStock.morning.facts(data, SCStock.avail, SCStock.model); return [f.reference.equity, f.matched, f.referenceWords]; });
      eq(name + ': from 4 November the reference is $30,000 at the same 0.5%', now, [30000, true, '$30,000 cash-account reference · $150 planned risk (0.5%) · $7,500 position cap (25%)']);
      const stale = await page.evaluate(() => { const data = JSON.parse(JSON.stringify(SCStock.data)); data.run.session = '2026-11-04'; const f = SCStock.morning.facts(data, SCStock.avail, SCStock.model); return [f.reference.equity, f.matched, f.sizing]; });
      check(name + ': a $2,000 publication measured from 4 November does not match and names the $30,000 reference', stale[0] === 30000 && stale[1] === false && /\$30,000/.test(stale[2]));
      eq(name + ': the day before the change keeps the old reference', await page.evaluate(() => [SCStock.morning.profileFor('2026-11-03').equity, SCStock.morning.profileFor('2026-11-04').equity, SCStock.morning.profileFor(null).equity]), [2000, 30000, 2000]);
    } finally { await tab.context.close(); }
  });
}
