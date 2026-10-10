/* Actual browser workflow over the run_evening-produced cash fixture. Private
   execution facts are deliberately manual; no broker or provider is contacted. */
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const DIR = 'tests/fixtures/cash-preview';
const NOW = '2026-09-11T13:35:00Z';
const KEY = 'spicystock:handoff:v1';
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const state = page => page.locator('[data-handoff-summary]').evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const resultAmounts = page => page.locator('[data-handoff-result-amounts]').evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const saved = page => page.evaluate(() => SCStock.handoff.list());
const set = async (page, fields) => { for (const [key, value] of Object.entries(fields)) await field(page, key).fill(value); };
async function save(page) {
  await page.locator('[data-handoff-save]').click();
  await page.waitForFunction(() => !document.querySelector('[data-handoff-save]').disabled || /storage|saving/i.test(document.querySelector('[data-handoff-storage]').textContent));
}

export async function checkHandoff({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- private handoff: explicit draft, cumulative fills/exits, correction and failure continuity');
  const observed = await readFile(path.join(ROOT, DIR, 'observed.json'), 'utf8');
  const halted = await readFile(path.join(ROOT, DIR, 'halted.json'), 'utf8');
  const launch = async (width, theme, extra, multiple = false) => {
    let sidecar = multiple ? await readFile(path.join(ROOT, DIR, 'observed-multiple.json'), 'utf8') : observed;
    const requests = [];
    const tab = await open(browser, base, '/' + DIR + '/publication' + (multiple ? '-multiple' : '') + '.json', NOW, width, {
      theme, hash: '#/explore/setting-up/COIL', reducedMotion: 'reduce', beforeLoad: async page => {
        page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: sidecar }));
        if (extra) await extra(page);
      }
    });
    await tab.page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.observations.facts().state));
    await tab.page.locator('#morning-open').click();
    await tab.page.locator('.ss-morning__prep > summary').click();
    return { ...tab, requests, halt: async () => { sidecar = halted; await tab.page.evaluate(() => SCStock.observations.reload()); await tab.page.waitForFunction(() => SCStock.observations.facts().state === 'loaded'); } };
  };
  const prepare = async page => {
    await page.locator('#morning-cash').fill('2000'); await page.locator('#morning-preview-fees').fill('1'); await page.locator('#morning-preview-quantity').fill('2');
    await page.locator('[data-handoff-prepare]').click();
    await page.waitForFunction(() => SCStock.handoff.list().length === 1);
  };
  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [390, 'dark'], [1280, 'light']]) {
    const tab = await launch(width, theme), { page, context, errors, requests } = tab;
    try {
      const before = await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), following: localStorage.getItem('spicystock:following:v1'), copies: [...document.querySelectorAll('[data-copy]')].map(node => node.dataset.copy) }));
      eq('private disclosure begins closed', await page.locator('#morning-handoffs').getAttribute('open'), null);
      eq('unknown cash cannot prepare', await page.locator('[data-handoff-prepare]').isDisabled(), true);
      await page.locator('#morning-cash').fill('2000');
      eq('unknown fees cannot prepare', await page.locator('[data-handoff-prepare]').isDisabled(), true);
      const requestCount = requests.length;
      await prepare(page);
      eq('preparation creates exactly one explicit private draft', (await saved(page)).map(item => [item.draft.quantity, item.plan.order.quantity, item.plan.order.then.quantity, item.report_updated_at]), [[2, 4, 4, null]]);
      eq('draft does not infer held, filled or submitted', [(await state(page))['Remaining reported holdings'], (await state(page))['Cumulative entry filled'], (await state(page))['Reported submitted']], ['Unknown', 'Unknown', 'Unknown']);
      eq('readback focuses its heading after explicit preparation', await page.evaluate(() => document.activeElement.id), 'handoff-title');
      await page.locator('[data-handoff-readback] > summary').click();
      check('readback labels personal two and original four separately', /BUY 2 COIL/.test(await page.locator('[data-handoff-text]').textContent()) && /Published quantity: 4/.test(await page.locator('[data-handoff-text]').textContent()));
      await page.locator('[data-handoff-copy]').click();
      check('clipboard contains chosen two and no submission claim', await page.evaluate(async () => /BUY 2 COIL/.test(await navigator.clipboard.readText()) && /places no order/.test(await navigator.clipboard.readText())));
      eq('copy does not invent a report', (await saved(page))[0].report_updated_at, null);
      await page.locator('[data-handoff-report] > summary').click();
      await set(page, { submitted_quantity: '2', submitted_at: '2026-09-11T08:33:00-05:00', filled_quantity: '1', average_price: '111.23', filled_at: '2026-09-11T08:34:00-05:00' });
      await save(page);
      eq('entry fill alone leaves remaining holdings unknown', [(await state(page))['Cumulative entry filled'], (await state(page))['Remaining reported holdings'], (await state(page))['Entry shares not filled']], ['1', 'Unknown', '1']);
      await set(page, { exited_quantity: '0' }); await save(page);
      eq('explicit no exits gives one held and one unfilled', [(await state(page))['Remaining reported holdings'], (await state(page))['Entry shares not filled'], (await state(page))['Entry remainder not reported cancelled']], ['1', '1', 'Unknown']);
      eq('reported facts disable new-entry readback copy', await page.locator('[data-handoff-copy]').isDisabled(), true);
      check('unknown protection stays explicit', /Protection is unknown/.test(await page.locator('[data-handoff-protection]').textContent()));
      await set(page, { cancelled_quantity: '1', cancelled_at: '2026-09-11T08:34:30-05:00', protected_quantity: '1', protection_confirmed_at: '2026-09-11T08:35:00-05:00' }); await save(page);
      eq('cancelled remainder is not an exit of held shares', [(await state(page))['Remaining reported holdings'], (await state(page))['Entry remainder not reported cancelled']], ['1', '0']);
      check('saved time shows Chicago', /8:35:00 AM CDT/.test((await state(page))['Protection checked by you']));
      check('matching manual protection never claims verified stop', /does not verify an active stop/.test(await page.locator('[data-handoff-protection]').textContent()));
      const revision = (await saved(page))[0].revision;
      await set(page, { filled_quantity: '2' }); await save(page);
      eq('impossible filled-plus-cancelled correction does not overwrite', (await saved(page))[0].revision, revision);
      eq('invalid correction preserves entered value', await field(page, 'filled_quantity').inputValue(), '2');
      check('invalid cumulative totals are explained', /cannot exceed/.test(await page.locator('[data-handoff-message]').textContent()));
      await page.locator('[data-handoff-reload]').click();
      eq('explicit reload discards bad correction', await field(page, 'filled_quantity').inputValue(), '1');
      await set(page, { average_price: '111.2345' }); await field(page, 'average_price').focus();
      await page.evaluate(() => { window.__reportInput = document.querySelector('[data-handoff-field="average_price"]'); SCStock.reclock(); });
      await tab.halt();
      eq('event refresh preserves exact unsaved field and focus', await field(page, 'average_price').evaluate(node => [node === window.__reportInput, node.value, document.activeElement === node]), [true, '111.2345', true]);
      eq('known halt withdraws preparation', await page.locator('[data-handoff-prepare]').isDisabled(), true);
      await page.evaluate(() => { SCStock.now = '2026-09-11T14:01:00Z'; SCStock.reclock(); });
      await save(page);
      eq('actual facts stay recordable after expiry and halt', (await saved(page))[0].report.average_price, '111.2345');
      await set(page, { exited_quantity: '1', exited_at: '2026-09-11T09:00:00-05:00' }); await save(page);
      eq('exit preserves entry history while reducing held shares', [(await state(page))['Cumulative entry filled'], (await state(page))['Reported exited'], (await state(page))['Remaining reported holdings']], ['1', '1', '0']);
      check('remaining protective sell needs reconciliation after exit', /exceeds/.test(await page.locator('[data-handoff-protection]').textContent()));
      eq('missing actual exit price and costs never borrow draft buffer', [(await state(page))['Draft fee buffer (estimate)'], await resultAmounts(page)], ['$1.00', {}]);
      await set(page, { average_price: '111.23', average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07' }); await save(page);
      eq('one filled share plus explicitly cancelled remainder gives reported net3.65', await resultAmounts(page), {
        'Reported gross result': '$3.77', 'Reported actual costs': '$0.12 (entry $0.05 + exit $0.07)', 'Reported net result': '$3.65'
      });
      check('completed gain remains expressly user-reported', /User-reported net gain/.test(await page.locator('[data-handoff-result-status]').textContent()) && /Broker records are not verified/.test(await page.locator('[data-handoff-completed]').textContent()));
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('[data-handoff-completed]').scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, 'reported-result-' + width + '-' + theme + '.png') }); }
      check('entry draft and published record remain separate', await page.evaluate(before => JSON.stringify(SCStock.data) === before.data && localStorage.getItem('spicystock:following:v1') === before.following, before));
      eq('no private report data reached a request', requests.slice(requestCount).map(request => [new URL(request.url).pathname, request.method, request.body]), [['/docs/morning.json', 'GET', null]]);
      check(width + '/' + theme + ': handoff fits phone and page', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('[data-handoff-summary]').scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, 'handoff-' + width + '-' + theme + '.png') }); }
      const raw = await page.evaluate(key => localStorage.getItem(key), KEY);
      await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
      await page.locator('#morning-open').click(); await page.locator('#morning-handoffs > summary').click();
      eq('reload retains private entry and exit facts exactly', await page.evaluate(key => localStorage.getItem(key), KEY), raw);
      eq('reload does not silently evict closed reported position', (await saved(page)).length, 1);
      eq('delete requires an explicit confirmation', await page.locator('[data-handoff-delete]').isDisabled(), true);
      await page.locator('[data-handoff-delete-confirm]').evaluate(node => { node.checked = true; node.dispatchEvent(new Event('change')); });
      await page.locator('[data-handoff-delete]').evaluate(node => node.click());
      await page.waitForFunction(() => SCStock.handoff.list().length === 0);
      check('deletion explains broker positions unchanged', /did not cancel an order or close a position/.test(await page.locator('[data-handoff-message]').textContent()));
      eq('handoff browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  const tab = await launch(1280, 'dark'), { page, context } = tab;
  try {
    await prepare(page); await page.locator('[data-handoff-report] > summary').click();
    await set(page, { submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0' });
    const other = await context.newPage();
    await other.goto(base + '/docs/index.html'); await other.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
    await other.evaluate(async () => { const item = SCStock.handoff.list()[0]; await SCStock.handoff.report(item.id, { ...item.report, submitted_quantity: '2', filled_quantity: '2', exited_quantity: '0' }, item.revision); });
    await page.waitForFunction(() => SCStock.handoff.list()[0].report.filled_quantity === 2);
    await page.waitForTimeout(100);
    check('cross-tab change is announced without silently adopting revision', /another view/.test(await page.locator('[data-handoff-editor-status]').textContent()));
    eq('cross-tab correction preserves unsaved value', await field(page, 'filled_quantity').inputValue(), '1');
    await save(page);
    eq('stale correction cannot overwrite other tab', (await saved(page))[0].report.filled_quantity, 2);
    check('revision conflict gives explicit recovery path', /Reopen|changed/.test(await page.locator('[data-handoff-message]').textContent()));
    await page.locator('[data-handoff-reload]').click();
    eq('explicit saved reload adopts new revision', await field(page, 'filled_quantity').inputValue(), '2');
    await set(page, { filled_quantity: '1' });
    await page.evaluate(() => { window.__realSet = Storage.prototype.setItem; Storage.prototype.setItem = function(key, value) { if (key === SCStock.handoff.KEY) throw Error('quota control'); return window.__realSet.call(this, key, value); }; });
    await save(page);
    eq('storage failure keeps old saved facts', (await saved(page))[0].report.filled_quantity, 2);
    eq('storage failure keeps correction for retry', await field(page, 'filled_quantity').inputValue(), '1');
    check('save failure offers private recovery without upload', await page.locator('[data-handoff-recovery]').isVisible() && /could not be confirmed/.test(await page.locator('[data-handoff-message]').textContent()));
    await page.evaluate(() => { Storage.prototype.setItem = window.__realSet; }); await save(page);
    eq('retry saves retained correction', (await saved(page))[0].report.filled_quantity, 1);
    await page.locator('[data-handoff-now="filled_at"]').click();
    check('use current time only fills the input', /^\d{4}-\d\d-\d\dT.*Z$/.test(await field(page, 'filled_at').inputValue()) && (await saved(page))[0].report.filled_at === null);
    for (const key of await page.evaluate(() => SCStock.handoff.FIELDS)) await field(page, key).fill('');
    await save(page);
    eq('explicit correction to unknown keeps reporting history', [(await saved(page))[0].report_updated_at !== null, (await state(page))['Remaining reported holdings']], [true, 'Unknown']);
    eq('clearing report fields cannot revive new entry copy or preparation', [await page.locator('[data-handoff-copy]').isDisabled(), await page.locator('[data-handoff-prepare]').isDisabled()], [true, true]);
    eq('unknown correction still remains editable', await page.locator('[data-handoff-save]').isDisabled(), false);
    await other.close();
  } finally { await context.close(); }

  const completedTab = await launch(390, 'light');
  try {
    const page = completedTab.page;
    await prepare(page); await page.locator('[data-handoff-report] > summary').click();
    const original = await page.evaluate(() => JSON.stringify({ record: SCStock.data, following: localStorage.getItem('spicystock:following:v1') }));
    const requestCount = completedTab.requests.length;
    const fullyExited = { submitted_quantity: '2', filled_quantity: '2', cancelled_quantity: '0', exited_quantity: '2', average_price: '111.23', average_exit_price: '115',
      filled_at: '2026-09-11T08:34:00-05:00', exited_at: '2026-09-11T09:00:00-05:00', entry_fees: '0.05', exit_fees: '0.07' };
    await set(page, fullyExited); await save(page);
    eq('two-share reported result uses actual fees rather than draft estimate', await resultAmounts(page), {
      'Reported gross result': '$7.54', 'Reported actual costs': '$0.12 (entry $0.05 + exit $0.07)', 'Reported net result': '$7.42'
    });
    eq('result does not change draft fee buffer', (await saved(page))[0].draft.fee_cents, 100);
    await set(page, { average_exit_price: '109.50' }); await save(page);
    eq('exit correction recomputes gross and net loss', [(await resultAmounts(page))['Reported gross result'], (await resultAmounts(page))['Reported net result']], ['-$3.46', '-$3.58']);
    check('loss is labelled only as user-reported', /User-reported net loss/.test(await page.locator('[data-handoff-result-status]').textContent()));
    for (const [name, patch] of [
      ['partial exit', { exited_quantity: '1' }], ['unknown cancellation', { cancelled_quantity: '' }],
      ['unknown entry price', { average_price: '' }], ['unknown exit price', { average_exit_price: '' }],
      ['unknown entry fees', { entry_fees: '' }], ['unknown exit fees', { exit_fees: '' }],
      ['undated entry fill', { filled_at: '' }], ['undated exit', { exited_at: '' }]
    ]) {
      await set(page, { ...fullyExited, ...patch }); await save(page);
      eq(name + ' withholds every completed amount', await resultAmounts(page), {});
      eq(name + ' never retains a stale gain/loss marker', await page.locator('[data-handoff-completed]').getAttribute('data-result-outcome'), 'unknown');
      check(name + ' explains an incomplete result', /Completed result unavailable/.test(await page.locator('[data-handoff-result-status]').textContent()));
    }
    await set(page, { ...fullyExited, entry_fees: '0', exit_fees: '0' }); await save(page);
    eq('explicit zero actual fees is accepted as zero, not unknown', [(await resultAmounts(page))['Reported actual costs'], (await resultAmounts(page))['Reported net result']], ['$0.00 (entry $0.00 + exit $0.00)', '$7.54']);
    await set(page, { average_exit_price: '111.23' }); await save(page);
    eq('exact zero net is the only break-even result', [(await resultAmounts(page))['Reported net result'], await page.locator('[data-handoff-completed]').getAttribute('data-result-outcome')], ['$0.00', 'breakeven']);
    for (const [price, display, outcome] of [['111.230001', '<$0.01', 'gain'], ['111.229999', '-<$0.01', 'loss']]) {
      await set(page, { average_exit_price: price }); await save(page);
      eq('sub-cent ' + outcome + ' retains exact sign without false zero', [(await resultAmounts(page))['Reported net result'], await page.locator('[data-handoff-completed]').getAttribute('data-result-outcome')], [display, outcome]);
    }
    await set(page, fullyExited); await save(page);
    await set(page, { exit_fees: '0.08' }); await field(page, 'exit_fees').focus();
    await page.evaluate(() => { window.__costInput = document.querySelector('[data-handoff-field="exit_fees"]'); SCStock.now = '2026-09-11T14:01:00Z'; SCStock.reclock(); });
    await completedTab.halt();
    eq('new cost correction keeps its node, draft and focus across expiry/event', await field(page, 'exit_fees').evaluate(node => [node === window.__costInput, node.value, document.activeElement === node]), [true, '0.08', true]);
    eq('unsaved fee edit does not alter saved completed result', (await resultAmounts(page))['Reported net result'], '$7.42');
    await save(page);
    eq('actual result correction remains available after entry expiry/event', (await resultAmounts(page))['Reported net result'], '$7.41');
    eq('result calculation does not mutate publication or following snapshots', await page.evaluate(() => JSON.stringify({ record: SCStock.data, following: localStorage.getItem('spicystock:following:v1') })), original);
    eq('private actual costs never reach a request', completedTab.requests.slice(requestCount).map(request => [new URL(request.url).pathname, request.method, request.body]), [['/docs/morning.json', 'GET', null]]);

    // A legacy private-store envelope, formed from an actual prepared/reporting
    // item, uses the prior eleven report fields. This is no publication change.
    const legacyRaw = await page.evaluate(() => {
      const item = SCStock.handoff.list()[0]; item.version = 1;
      for (const key of ['average_exit_price', 'entry_fees', 'exit_fees']) delete item.report[key];
      const raw = JSON.stringify({ version: 1, items: [item] }); localStorage.setItem(SCStock.handoff.KEY, raw); return raw;
    });
    await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
    await page.locator('#morning-open').click(); await page.locator('#morning-handoffs > summary').click(); await page.locator('[data-handoff-report] > summary').click();
    eq('reading legacy store performs no write', await page.evaluate(key => localStorage.getItem(key), KEY), legacyRaw);
    eq('legacy report fields survive with new fields unknown', [(await state(page))['Cumulative entry filled'], (await state(page))['Reported exited'], await field(page, 'average_exit_price').inputValue(), await field(page, 'entry_fees').inputValue(), await field(page, 'exit_fees').inputValue()], ['2', '2', '', '', '']);
    eq('legacy report does not acquire a fabricated result', await resultAmounts(page), {});
    await set(page, { average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.001' }); await save(page);
    eq('invalid new fees do not migrate or overwrite legacy bytes', await page.evaluate(key => localStorage.getItem(key), KEY), legacyRaw);
    eq('invalid actual fee correction remains editable', await field(page, 'exit_fees').inputValue(), '0.001');
    await set(page, { exit_fees: '0.07' }); await save(page);
    eq('explicit valid report save advances store version', await page.evaluate(key => JSON.parse(localStorage.getItem(key)).version, KEY), 2);
    eq('explicit legacy completion computes the known reported net', (await resultAmounts(page))['Reported net result'], '$7.42');
    check('completed result and form still fit phone', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
    if (shotsDir) { await field(page, 'entry_fees').scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, 'reported-result-form-390-light.png') }); }
    eq('completed-result browser errors', [...completedTab.errors], []);
  } finally { await completedTab.context.close(); }

  const multi = await launch(390, 'light', null, true);
  try {
    const page = multi.page;
    await page.locator('#morning-preview-plan').selectOption('setting-up:COIL'); await prepare(page);
    await page.locator('[data-handoff-report] > summary').click(); await set(page, { submitted_quantity: '2' });
    await page.locator('#morning-preview-plan').selectOption('bursts:AAPL');
    await page.locator('#morning-preview-fees').fill('1'); await page.locator('#morning-preview-quantity').fill('1');
    await page.locator('[data-handoff-prepare]').click();
    await page.waitForFunction(() => !document.querySelector('[data-handoff-prepare]').disabled);
    eq('preparing another plan cannot discard a dirty report', [(await saved(page)).length, await field(page, 'submitted_quantity').inputValue(), await page.locator('#handoff-title').textContent()], [1, '2', 'COIL · personal broker record']);
    check('other-plan preparation gives explicit save/discard path', /Save your current broker report/.test(await page.locator('[data-handoff-prepare-status]').textContent()));
    await page.locator('[data-handoff-reload]').click();
    await page.evaluate(() => {
      const locks = navigator.locks, original = locks.request.bind(locks);
      window.__releasePrepare = null;
      locks.request = (name, callback) => new Promise(resolve => { window.__releasePrepare = () => resolve(original(name, callback)); });
      window.__restoreLocks = () => { locks.request = original; };
    });
    await page.locator('[data-handoff-prepare]').click();
    await page.waitForFunction(() => !!window.__releasePrepare);
    await set(page, { submitted_quantity: '2' }); await field(page, 'submitted_quantity').focus();
    await page.evaluate(() => { window.__releasePrepare(); window.__restoreLocks(); });
    await page.waitForFunction(() => SCStock.handoff.list().length === 2);
    eq('report begun during pending preparation survives completion', [await field(page, 'submitted_quantity').inputValue(), await page.locator('#handoff-title').textContent()], ['2', 'COIL · personal broker record']);
    check('pending preparation preserves editor focus', await field(page, 'submitted_quantity').evaluate(node => document.activeElement === node));
    eq('published independent quantities stay unchanged', await page.evaluate(() => SCStock.handoff.list().map(item => [item.plan.ticker, item.draft.quantity, item.plan.order.quantity])), [['COIL', 2, 4], ['AAPL', 1, 1]]);
  } finally { await multi.context.close(); }

  for (const [label, control] of [
    ['Web Locks unavailable', page => page.addInitScript(() => Object.defineProperty(navigator, 'locks', { value: undefined }))],
    ['future storage version', page => page.addInitScript(() => localStorage.setItem('spicystock:handoff:v1', '{"version":999,"items":[]}'))]
  ]) {
    const { page, context } = await launch(390, 'light', control);
    try {
      await page.locator('#morning-cash').fill('2000'); await page.locator('#morning-preview-fees').fill('0');
      eq(label + ' refuses preparation without breaking cash preview', [await page.locator('[data-handoff-prepare]').isDisabled(), await page.locator('[data-cash-preview]').getAttribute('data-preview-state')], [true, 'calculated']);
      await page.locator('#morning-handoffs > summary').click();
      check(label + ' explains read-only/unreadable state', /unavailable|unreadable|another version|isn’t available/.test(await page.locator('[data-handoff-storage]').textContent()));
      if (label === 'future storage version') eq('unknown store left byte-exact', await page.evaluate(key => localStorage.getItem(key), KEY), '{"version":999,"items":[]}');
    } finally { await context.close(); }
  }
  for (const module of ['app-handoff.js', 'app-handoff-ui.js']) {
    const { page, context, errors } = await launch(390, 'light', page => page.route('**/' + module, route => route.fulfill({ contentType: 'text/javascript', body: '/* unavailable optional module control */' })));
    try {
      await page.locator('#morning-cash').fill('2000'); await page.locator('#morning-preview-fees').fill('0');
      eq(module + ' absence leaves cash and morning usable', [await page.locator('[data-cash-preview]').getAttribute('data-preview-state'), await page.locator('html').getAttribute('data-ss-rendered')], ['calculated', 'fresh']);
      check(module + ' fallback names unavailable private function', /Private broker handoffs are unavailable/.test(await page.locator('#morning-desk').textContent()));
      eq(module + ' absence raises no page errors', [...errors], []);
    } finally { await context.close(); }
  }
}
