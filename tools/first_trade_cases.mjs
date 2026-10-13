/* The first-trade rehearsal (#110): one journey through the real page, from the
   admitted tickets of the run_evening-produced $2,000 cash fixture to the
   private backup the page downloads. Cash is refused until it is entered and
   funds a whole share; two drafts are prepared; the reported broker facts
   carry a partial fill, the remainder cancelled at the cutoff, a partial exit,
   a gap through the protective stop, and fees. Every broker fact here is
   SYNTHETIC: no broker, provider or real trade is involved.

   The downloaded bytes and the amounts the page printed are held to
   tests/fixtures/first-trade/ (SCSTOCK_FIRST_TRADE_WRITE=1 writes them), so
   tools/private_results.py can be tested on exactly what the page writes. The
   page clock is a fixed Date the suite moves step by step, so the backup's own
   clocks are the journey's and two runs write the same bytes. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const SOURCE = 'tests/fixtures/cash-preview';
export const OUT = 'tests/fixtures/first-trade';
const KEY = 'spicystock:handoff:v1';
const START = '2026-09-11T13:35:00.000Z';
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const facts = (page, selector) => page.locator(selector).evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const saved = page => page.evaluate(() => SCStock.handoff.list());

export async function checkFirstTrade({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- first-trade rehearsal: refused cash, two drafts, partial fill, cutoff cancel, partial exit, a gap through the stop, the backup');
  const sidecar = await readFile(path.join(ROOT, SOURCE, 'observed-multiple.json'), 'utf8');
  const write = process.env.SCSTOCK_FIRST_TRADE_WRITE === '1';
  const runs = [];
  for (const [width, theme] of [[390, 'light'], [1280, 'dark']]) {
    const requests = [];
    const tab = await open(browser, base, '/' + SOURCE + '/publication-multiple.json', START, width, {
      theme, hash: '#/explore/setting-up/COIL', reducedMotion: 'reduce', beforeLoad: async (page, context) => {
        await context.addInitScript(start => {
          const Native = Date; window.__rehearsalClock = Native.parse(start);
          window.Date = class extends Native { constructor(...args) { super(...(args.length ? args : [window.__rehearsalClock])); } static now() { return window.__rehearsalClock; } };
        }, START);
        page.on('request', request => requests.push([new URL(request.url()).pathname, request.method(), request.postData()]));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: sidecar }));
      }
    });
    const { page, context, errors } = tab;
    const name = width + '/' + theme;
    // The page's own clock (SCStock.now) and the Date the private store stamps
    // move together, as they would on a real morning and the days after it.
    const at = async iso => page.evaluate(iso => { window.__rehearsalClock = Date.parse(iso); SCStock.now = iso; SCStock.reclock(); }, iso);
    const set = async fields => { for (const [key, value] of Object.entries(fields)) await field(page, key).fill(value); };
    const save = async () => {
      const before = await page.evaluate(() => JSON.stringify(SCStock.handoff.list().map(item => item.revision)));
      await page.locator('[data-handoff-save]').click();
      await page.waitForFunction(before => JSON.stringify(SCStock.handoff.list().map(item => item.revision)) !== before, before);
    };
    const choose = async ticker => {
      const id = (await saved(page)).find(item => item.plan.ticker === ticker).id;
      await page.locator('#handoff-select').selectOption(id);
      await page.waitForFunction(ticker => document.querySelector('#handoff-title').textContent.startsWith(ticker + ' '), ticker);
    };
    const preview = async (plan, cash, fees, quantity) => {
      await page.locator('#morning-preview-plan').selectOption(plan);
      await page.locator('#morning-cash').fill(cash); await page.locator('#morning-preview-fees').fill(fees); await page.locator('#morning-preview-quantity').fill(quantity);
      return [await page.locator('[data-cash-preview]').getAttribute('data-preview-state'), await page.locator('[data-handoff-prepare]').isDisabled()];
    };
    const status = async () => page.locator('[data-handoff-summary]').evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
    try {
      await page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.observations.facts().state));
      await page.locator('#morning-open').click();
      await page.locator('.ss-morning__prep > summary').click();
      const before = await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), following: localStorage.getItem('spicystock:following:v1') }));

      // 8:35 AM CDT, inside the 8:30-9:00 entry window. Cash the broker has not
      // confirmed produces no ready state; neither does cash that cannot fund it.
      eq(name + ': unconfirmed cash gives no ready state', await preview('setting-up:COIL', '', '1', '3'), ['needs_cash', true]);
      eq(name + ': unreadable cash is refused', await preview('setting-up:COIL', 'two thousand', '1', '3'), ['invalid_cash', true]);
      eq(name + ': zero settled cash funds no share', await preview('setting-up:COIL', '0', '1', '3'), ['unfunded', true]);
      eq(name + ': $300 funds two shares at the limit, not three', await preview('setting-up:COIL', '300', '1', '3'), ['invalid_quantity', true]);
      check(name + ': the refusal names the most the cash funds', /Choose 1–2 whole shares/.test(await page.locator('[data-cash-preview-status]').textContent()));
      eq(name + ': $2,000 settled cash funds the chosen three', await preview('setting-up:COIL', '2000', '1', '3'), ['calculated', false]);
      const coilPreview = await facts(page, '[data-cash-preview-result]');
      eq(name + ': COIL preview at the published limit', [coilPreview['Published shares'], coilPreview['Your preview shares'], coilPreview['Principal at the limit'], coilPreview['Planned price-to-stop risk'], coilPreview['Total cash for this preview']], ['4', '3', '$335.16', '$6.66', '$336.16']);
      await page.locator('[data-handoff-prepare]').click(); await page.waitForFunction(() => SCStock.handoff.list().length === 1);
      eq(name + ': AAPL preview of its one published share', await preview('bursts:AAPL', '2000', '1', '1'), ['calculated', false]);
      const aaplPreview = await facts(page, '[data-cash-preview-result]');
      eq(name + ': AAPL preview at the published limit', [aaplPreview['Principal at the limit'], aaplPreview['Planned price-to-stop risk']], ['$63.22', '$2.52']);
      await page.locator('[data-handoff-prepare]').click(); await page.waitForFunction(() => SCStock.handoff.list().length === 2);
      eq(name + ': two drafts, each its own quantity beside the published one', (await saved(page)).map(item => [item.plan.ticker, item.draft.quantity, item.plan.order.quantity, item.report_updated_at]), [['COIL', 3, 4, null], ['AAPL', 1, 1, null]]);
      await page.locator('[data-handoff-readback] > summary').click();
      await page.locator('[data-handoff-copy]').click();
      check(name + ': the readback copied names the draft and submits nothing', await page.evaluate(async () => { const text = await navigator.clipboard.readText(); return /BUY 1 AAPL · STOP LIMIT · trigger \$62\.10 · limit \$63\.22/.test(text) && /STOP \$60\.70/.test(text) && /places no order/.test(text); }));
      await page.locator('[data-handoff-report] > summary').click();
      const reporting = requests.length;

      // 8:41: the broker reports AAPL filled in full and COIL two of three.
      await at('2026-09-11T13:41:00.000Z');
      await set({ submitted_quantity: '1', submitted_at: '2026-09-11T08:32:00-05:00', filled_quantity: '1', average_price: '62.40', filled_at: '2026-09-11T08:36:20-05:00',
        cancelled_quantity: '0', exited_quantity: '0', protected_quantity: '1', protection_confirmed_at: '2026-09-11T08:37:00-05:00' });
      await save();
      eq(name + ': AAPL filled and protected', [(await status())['Remaining reported holdings'], await page.locator('[data-handoff-completed]').getAttribute('data-result-state')], ['1', 'incomplete']);
      check(name + ': matched protection is the owner’s word, never verified', /does not verify an active stop/.test(await page.locator('[data-handoff-protection]').textContent()));
      await choose('COIL');
      await set({ submitted_quantity: '3', submitted_at: '2026-09-11T08:31:10-05:00', filled_quantity: '2', average_price: '111.05', filled_at: '2026-09-11T08:33:40-05:00',
        exited_quantity: '0', protected_quantity: '2', protection_confirmed_at: '2026-09-11T08:34:05-05:00' });
      await save();
      eq(name + ': COIL partly filled, its remainder not yet reported cancelled', [(await status())['Entry shares not filled'], (await status())['Entry remainder not reported cancelled'], (await status())['Remaining reported holdings']], ['1', 'Unknown', '2']);
      eq(name + ': a reported fill withdraws the new-entry copy', await page.locator('[data-handoff-copy]').isDisabled(), true);

      // 9:02, past the cutoff: no new draft, but the remainder's cancellation
      // at 9:00 is still recordable.
      await at('2026-09-11T14:02:00.000Z');
      eq(name + ': no new draft after the entry window', await page.locator('[data-handoff-prepare]').isDisabled(), true);
      await set({ cancelled_quantity: '1', cancelled_at: '2026-09-11T09:00:00-05:00' }); await save();
      eq(name + ': the remainder cancelled at the cutoff', [(await status())['Unfilled shares cancelled'], (await status())['Entry remainder not reported cancelled']], ['1', '0']);

      // Monday 14 September. AAPL opens under its stop; the stop fills at
      // $59.85, $0.85 under $60.70: a gap through the stop.
      await at('2026-09-14T13:40:00.000Z');
      await choose('AAPL');
      await set({ exited_quantity: '1', exited_at: '2026-09-14T08:30:02-05:00', average_exit_price: '59.85', entry_fees: '0', exit_fees: '0.01', protected_quantity: '0', protection_confirmed_at: '2026-09-14T08:31:00-05:00' });
      await save();
      const aaplResult = await facts(page, '[data-handoff-result-amounts]');
      eq(name + ': AAPL loss and the part of it past the stop', aaplResult, {
        'Reported gross result': '-$2.55', 'Reported actual costs': '$0.01 (entry $0.00 + exit $0.01)', 'Reported net result': '-$2.56',
        'Average exit below the published stop': '$0.85 a share · $0.85 on 1 reported share past the stop (a gap or slippage)'
      });
      eq(name + ': the loss is the owner’s, reported', [await page.locator('[data-handoff-completed]').getAttribute('data-result-outcome'), /User-reported net loss/.test(await page.locator('[data-handoff-result-status]').textContent())], ['loss', true]);
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('[data-handoff-completed]').scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, 'first-trade-gap-' + width + '-' + theme + '.png') }); }
      // COIL sells one at $113.20 into strength that afternoon.
      await at('2026-09-14T20:00:00.000Z');
      await choose('COIL');
      await set({ exited_quantity: '1', exited_at: '2026-09-14T14:55:00-05:00', average_exit_price: '113.20', protected_quantity: '1', protection_confirmed_at: '2026-09-14T14:56:00-05:00' });
      await save();
      eq(name + ': a partial exit has no completed result', [await page.locator('[data-handoff-completed]').getAttribute('data-result-state'), await facts(page, '[data-handoff-result-amounts]')], ['incomplete', {}]);
      check(name + ': the partial exit says why', /not fully exited/.test(await page.locator('[data-handoff-result-status]').textContent()));
      check(name + ': one share remains by the owner’s report', /reported remaining holdings are 1 whole share/.test(await page.locator('[data-handoff-exit-review]').textContent()));

      // Tuesday 15 September, the day-3 close: the last share at $114.00, so
      // the two exits average $113.60.
      await at('2026-09-15T20:10:00.000Z');
      await set({ exited_quantity: '2', exited_at: '2026-09-15T14:59:00-05:00', average_exit_price: '113.60', entry_fees: '0', exit_fees: '0.02', protected_quantity: '0', protection_confirmed_at: '2026-09-15T15:00:00-05:00' });
      await save();
      const coilResult = await facts(page, '[data-handoff-result-amounts]');
      eq(name + ': COIL gain on the two shares filled', coilResult, { 'Reported gross result': '$5.10', 'Reported actual costs': '$0.02 (entry $0.00 + exit $0.02)', 'Reported net result': '$5.08' });
      eq(name + ': the published records are untouched', await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), following: localStorage.getItem('spicystock:following:v1') })), before);

      // The backup, downloaded as the owner would keep it.
      await at('2026-09-15T21:00:00.000Z');
      if (!await page.locator('#morning-handoffs').evaluate(node => node.open)) await page.locator('#morning-handoffs > summary').click();
      if (!await page.locator('[data-handoff-backup]').evaluate(node => node.open)) await page.locator('[data-handoff-backup] > summary').click();
      const waiting = page.waitForEvent('download'); await page.locator('[data-handoff-backup-download]').click();
      const download = await waiting, raw = await readFile(await download.path(), 'utf8');
      eq(name + ': the download is the stored bytes exactly', raw, await page.evaluate(key => localStorage.getItem(key), KEY));
      const printed = {};
      for (const ticker of ['COIL', 'AAPL']) {
        await choose(ticker);
        const summary = await status();
        printed[ticker] = {
          draft_cash: summary['Draft cash at limit including buffer'], draft_risk: summary['Draft price-to-stop risk'],
          outcome: await page.locator('[data-handoff-completed]').getAttribute('data-result-outcome'),
          amounts: await facts(page, '[data-handoff-result-amounts]')
        };
      }
      // From the first report on, the page asked for nothing but the published
      // morning file, and nothing it asked for carried a body.
      eq(name + ': no reported fact left the page', requests.slice(reporting).filter(([pathname, method, body]) => pathname !== '/docs/morning.json' || method !== 'GET' || body), []);
      check(name + ': no request carried a body', requests.every(([, method, body]) => method === 'GET' && !body));
      check(name + ': the desk fits the screen', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      eq(name + ': no browser error', [...errors], []);
      runs.push({ raw, printed });
    } catch (error) {
      check(name + ': the rehearsal completes', false, error.stack);
    } finally { await context.close(); }
  }
  if (runs.length !== 2) return;
  eq('the phone and the desktop journeys write the same backup', runs[1].raw, runs[0].raw);
  eq('and print the same amounts', runs[1].printed, runs[0].printed);
  const printed = JSON.stringify({ publication: SOURCE + '/publication-multiple.json', records: runs[0].printed }, null, 2) + '\n';
  const target = path.join(ROOT, OUT);
  if (write) {
    await mkdir(target, { recursive: true });
    await writeFile(path.join(target, 'backup.json'), runs[0].raw);
    await writeFile(path.join(target, 'page-results.json'), printed);
    console.log('   wrote ' + OUT + '/backup.json and page-results.json');
    return;
  }
  const committed = async file => { try { return await readFile(path.join(target, file), 'utf8'); } catch (error) { return null; } };
  eq('the committed backup is what the page writes (SCSTOCK_FIRST_TRADE_WRITE=1 regenerates)', runs[0].raw, await committed('backup.json'));
  eq('the committed amounts are what the page prints', printed, await committed('page-results.json'));
}
