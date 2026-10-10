/* Offline browser controls. Public inputs are frozen producer publications;
   all execution facts and legacy private storage below are explicitly synthetic.
   No real profile, broker, provider, upload or live publication is used. */
import { readFile, mkdir } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const KEY = 'spicystock:handoff:v1';
const sha = raw => createHash('sha256').update(raw).digest('hex');
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const saved = page => page.evaluate(() => SCStock.handoff.list());
const rawStore = page => page.evaluate(key => localStorage.getItem(key), KEY);
const text = (page, selector) => page.locator(selector).textContent();
const set = async (page, fields) => { for (const [key, value] of Object.entries(fields)) await field(page, key).fill(value); };
const summary = page => page.locator('[data-handoff-summary]').evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const amounts = page => page.locator('[data-handoff-result-amounts]').evaluate(node => Object.fromEntries([...node.children].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent])));
const partial = { submitted_quantity: '9', submitted_at: '2026-10-09T14:00:00Z', filled_quantity: '7', average_price: '31.234567', filled_at: '2026-10-09T14:01:00Z', cancelled_quantity: '2', cancelled_at: '2026-10-09T14:02:00Z', exited_quantity: '3', exited_at: '2026-10-09T15:00:00Z', protected_quantity: '5', protection_confirmed_at: '2026-10-09T15:01:00Z' };
const complete = { exited_quantity: '7', average_exit_price: '32.345678', exited_at: '2026-10-09T16:00:00Z', entry_fees: '0.11', exit_fees: '0.22' };

async function producer(name) {
  const stem = path.join(ROOT, 'tests/fixtures/stop-research', name);
  const [canonical, reader, receiptRaw, bundleRaw] = await Promise.all([
    readFile(stem + '-publication.json.gz').then(gunzipSync), readFile(stem + '-reader.json.gz').then(gunzipSync),
    readFile(stem + '-receipt.json'), readFile(stem + '-bundle.json')
  ]);
  const receipt = JSON.parse(receiptRaw), bundle = JSON.parse(bundleRaw);
  return { name, canonical, reader, receiptRaw, bundleRaw, receipt, bundle,
    now: new Date(Date.parse(receipt.timing.generated_at) + 60000).toISOString() };
}
async function save(page) {
  await page.locator('[data-handoff-save]').click();
  await page.waitForFunction(() => !document.querySelector('[data-handoff-save]').disabled || /storage|saving/i.test(document.querySelector('[data-handoff-storage]').textContent));
}
async function reveal(page) {
  if (!await page.locator('#morning-desk').evaluate(node => node.open)) await page.locator('#morning-open').click();
  if (!await page.locator('[data-stop-research]').evaluate(node => node.open)) await page.locator('[data-stop-research] > summary').click();
  await page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.stopResearch.status().state));
}
async function openReport(page, ticker) { await page.locator('[data-stop-report="' + ticker + '"]').click(); }

export async function checkIndependentReports({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- independent reports: synthetic actual facts, original research identity, no order authority');
  const launch = async (fixture, { width = 1280, theme = 'dark', seed = null } = {}) => {
    const requests = [], state = { fixture };
    const tab = await open(browser, base, null, fixture.now, width, {
      theme, lens: 'all', reducedMotion: 'reduce', hash: '#/explore/setting-up', beforeLoad: async (page, context) => {
        page.setDefaultTimeout(5000);
        await context.addInitScript(({ now, key, seed }) => {
          // Explicit offline clock: report validation uses Date as well as SCStock.now.
          const NativeDate = Date;
          window.__reportClock = Date.parse(now);
          window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [window.__reportClock])); } static now() { return window.__reportClock; } };
          if (seed !== null) localStorage.setItem(key, seed);
          window.__reportCopies = 0;
          Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { window.__reportCopies++; } } });
        }, { now: fixture.now, key: KEY, seed });
        context.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
        await context.route('**/*', async route => {
          const url = new URL(route.request().url()), f = state.fixture;
          if (url.origin !== base) { await route.fulfill({ contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'application/json', body: url.hostname === 'fonts.googleapis.com' ? '' : '{}' }); return; }
          if (url.pathname === '/docs/reader.json') { await route.fulfill({ contentType: 'application/json', body: f.reader }); return; }
          if (url.pathname === '/docs/morning.json') { await route.fulfill({ contentType: 'application/json', body: '{}' }); return; }
          if (url.pathname === '/docs/stop-research.json') { await route.fulfill({ contentType: 'application/json', body: f.receiptRaw }); return; }
          if (url.pathname.startsWith('/docs/stop-research/')) { await route.fulfill({ contentType: 'application/json', body: f.bundleRaw }); return; }
          await route.continue();
        });
      }
    });
    await tab.page.waitForFunction(() => SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    return { ...tab, requests, state };
  };
  const capture = async (page, name) => { if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, name + '.png') }); } };
  const authority = page => page.evaluate(() => ({ data: JSON.stringify(SCStock.data), model: JSON.stringify(SCStock.model), following: localStorage.getItem('spicystock:following:v1') }));
  const privacy = async (tab, start, name) => {
    eq(name + ': reporting adds no HTTP request or private request body', tab.requests.slice(start), []);
    eq(name + ': reporting cannot copy an order', await tab.page.evaluate(() => window.__reportCopies), 0);
    eq(name + ': no uncaught browser errors', Array.from(tab.errors), []);
  };
  const run = async (name, fn) => { try { await fn(); } catch (error) { check('independent reports ' + name + ': workflow completes', false, error.stack); } };

  await run('retained actual zero-ticket path', async () => {
    const fixture = await producer('current');
    for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
      const name = 'retained ' + width + '/' + theme, tab = await launch(fixture, { width, theme }), { page } = tab;
      try {
        eq(name + ': frozen original canonical and reader bytes bind', await page.evaluate(() => [SCStock.observations.facts().canonicalHash, SCStock.observations.facts().recordHash]), [sha(fixture.canonical), sha(fixture.reader)]);
        eq(name + ': actual publication has no admitted tickets', JSON.parse(fixture.canonical).trades.length, 0);
        eq(name + ': empty private storage has no inferred execution', [await rawStore(page), (await saved(page)).length], [null, 0]);
        await reveal(page);
        eq(name + ': original five qualified rows offer reporting', await page.locator('[data-stop-report]').evaluateAll(nodes => nodes.map(node => node.dataset.stopReport)), fixture.bundle.rows.map(row => row.ticker));
        const before = await authority(page), requestStart = tab.requests.length;
        await page.locator('.ss-morning__prep > summary').click();
        eq(name + ': settled cash remains unknown and cannot prepare', [await page.locator('#morning-cash').inputValue(), await page.locator('[data-handoff-prepare]').isDisabled()], ['', true]);
        await page.locator('[data-stop-report="KE"]').focus(); await page.keyboard.press('Enter');
        eq(name + ': open creates only a transient blank editor', await page.locator('#morning-handoffs').getAttribute('data-handoff-mode'), 'independent-unsaved');
        eq(name + ': keyboard reporting focuses its heading', await page.evaluate(() => document.activeElement.id), 'handoff-title');
        eq(name + ': every actual field is blank including quantity, fees and prices', await page.locator('[data-handoff-field]').evaluateAll(nodes => nodes.map(node => node.value)), Array(14).fill(''));
        eq(name + ': opening creates no private record', [await rawStore(page), (await saved(page)).length], [null, 0]);
        check(name + ': original not-admitted source and no entry permission remain explicit', /Original production baseline: not admitted.*grants no entry permission/.test(await text(page, '[data-handoff-research-source]')));
        eq(name + ': verbose source references begin as a closed disclosure', await page.locator('[data-handoff-research-references]').evaluate(node => node.open), false);
        const refs = [fixture.receipt.publication.data_sha256, fixture.receipt.bundle.sha256, fixture.bundle.rows.find(row => row.ticker === 'KE').evidence.id];
        check(name + ': original canonical/cohort/evidence references remain available', await page.locator('[data-handoff-research-digests]').evaluate((node, refs) => refs.every(value => node.textContent.includes(value)), refs));
        eq(name + ': report-only editor has no visible readback and no order copy', [await page.locator('[data-handoff-readback]').isVisible(), await page.locator('[data-handoff-copy]').isDisabled()], [false, true]);
        await page.locator('#handoff-title').scrollIntoViewIfNeeded(); await capture(page, 'independent-blank-' + width + '-' + theme);
        await save(page);
        eq(name + ': blank first save refuses and writes nothing', await rawStore(page), null);
        await set(page, { submitted_quantity: '1', filled_quantity: '0' }); await save(page);
        eq(name + ': zero fill never becomes an executed trade', await rawStore(page), null);
        await set(page, { submitted_quantity: '', filled_quantity: '1' }); await save(page);
        eq(name + ': positive fill without actual submitted total refuses', await rawStore(page), null);
        eq(name + ': invalid save preserves explicitly entered positive fill', await field(page, 'filled_quantity').inputValue(), '1');
        await field(page, 'average_price').fill('31.234567'); await field(page, 'average_price').focus();
        await page.evaluate(() => { window.__independentInput = document.querySelector('[data-handoff-field="average_price"]'); });
        await page.locator('#morning-close').click(); await page.locator('#morning-open').click();
        eq(name + ': modal close/reopen preserves exact unsaved input node and value', await field(page, 'average_price').evaluate(node => [node === window.__independentInput, node.value]), [true, '31.234567']);
        await page.locator('[data-handoff-cancel]').click();
        eq(name + ': explicit cancellation discards transient facts with no write', [await rawStore(page), (await saved(page)).length], [null, 0]);
        await openReport(page, 'KE'); await set(page, partial); await save(page);
        const item = (await saved(page))[0], row = fixture.bundle.rows.find(row => row.ticker === 'KE');
        check(name + ': explicit actual seven-share fill is saved without research sizing cap', !!item && item.report.filled_quantity === 7 && row.research.shares === 1);
        if (!item) return;
        eq(name + ': report-only discriminant excludes plan/draft/order/cash', Object.keys(item).sort(), ['version', 'kind', 'id', 'revision', 'created_at', 'updated_at', 'source', 'report', 'report_updated_at'].sort());
        eq(name + ': exact original source is frozen', item.source, { ticker: 'KE', stage: 'setting-up', publication: fixture.receipt.publication, cohort: { sha256: fixture.receipt.bundle.sha256, bytes: fixture.receipt.bundle.bytes, generated_at: fixture.receipt.timing.generated_at, policy_id: fixture.receipt.policy.id }, evidence: row.evidence, baseline_admitted: false });
        eq(name + ': actual terms and times differ from model and remain unchanged', [item.report.average_price, item.report.filled_at, item.report.submitted_quantity], ['31.234567', '2026-10-09T14:01:00.000Z', 9]);
        const facts = await summary(page);
        eq(name + ': actual partial exit conserves seven entry fills and four holdings', [facts['Cumulative entry filled'], facts['Reported exited'], facts['Remaining reported holdings'], facts['Entry remainder not reported cancelled']], ['7', '3', '4', '0']);
        check(name + ': over-protection remains a visible reconciliation fact', /exceeds remaining/.test(await text(page, '[data-handoff-protection]')));
        eq(name + ': independent report never inherits draft quantity or cash arithmetic', await page.evaluate(id => { const s = SCStock.handoff.summary(SCStock.handoff.find(id)); return [s.planned_quantity, s.calculation, SCStock.handoff.readback(SCStock.handoff.find(id)), SCStock.handoff.copy(id).ok]; }, item.id), [null, null, '', false]);
        eq(name + ': saved independent report keeps entry readback and archived instructions hidden', [await page.locator('[data-handoff-readback]').isVisible(), await page.locator('[data-handoff-exits]').locator('li').count()], [false, 0]);
        eq(name + ': partial exit result remains incomplete', await amounts(page), {});
        const prior = await rawStore(page);
        await set(page, { filled_quantity: '8' }); await save(page);
        eq(name + ': impossible fill plus cancellation refuses without write', await rawStore(page), prior);
        eq(name + ': invalid actual correction stays in the editor', await field(page, 'filled_quantity').inputValue(), '8');
        await page.locator('[data-handoff-reload]').click();
        await set(page, complete); await save(page);
        eq(name + ': fully exited actual facts calculate exact gross/net without model prices', await page.evaluate(id => { const r = SCStock.handoff.summary(SCStock.handoff.find(id)).completed_result; return [r.gross_microusd, r.fees_microusd, r.net_microusd, r.net_display, r.outcome]; }, item.id), ['7777777', '330000', '7447777', '$7.45', 'gain']);
        eq(name + ': visible user-reported net uses actual costs', (await amounts(page))['Reported net result'], '$7.45');
        await page.locator('[data-handoff-completed]').scrollIntoViewIfNeeded(); await capture(page, 'independent-completed-' + width + '-' + theme);
        await field(page, 'exit_fees').fill(''); await save(page);
        eq(name + ': unknown actual costs clear previous completed amounts', await amounts(page), {});
        eq(name + ': unknown fees never borrow a draft estimate', (await saved(page))[0].report.exit_fees, null);
        await field(page, 'exit_fees').fill('0.22'); await save(page);
        await field(page, 'exited_at').fill(''); await save(page);
        eq(name + ': missing actual exit clock withdraws completed result', await amounts(page), {});
        await field(page, 'exited_at').fill(complete.exited_at); await save(page);
        await set(page, { cancelled_quantity: '', cancelled_at: '' }); await save(page);
        eq(name + ': unknown submitted remainder cancellation cannot imply reconciliation', await amounts(page), {});
        await set(page, { cancelled_quantity: partial.cancelled_quantity, cancelled_at: partial.cancelled_at }); await save(page);
        const originalSource = JSON.stringify((await saved(page))[0].source), persisted = await rawStore(page);
        await openReport(page, 'KE');
        eq(name + ': same-source action opens saved item without overwrite or duplicate', [await rawStore(page), (await saved(page)).length], [persisted, 1]);
        eq(name + ': original source remains unchanged after repeated reporting action', JSON.stringify((await saved(page))[0].source), originalSource);
        await field(page, 'average_price').fill('30.75'); await field(page, 'average_price').focus();
        await page.evaluate(() => { window.__dirtyReport = document.querySelector('[data-handoff-field="average_price"]'); });
        await openReport(page, 'PSNL');
        eq(name + ': switching research rows refuses to erase dirty private fields', await field(page, 'average_price').evaluate(node => [node === window.__dirtyReport, node.value]), [true, '30.75']);
        check(name + ': dirty-switch refusal is explicit on requested row', /unsaved|kept|discard/i.test(await text(page, '[data-stop-row="PSNL"] [data-stop-report-status]')));
        eq(name + ': zero-ticket source/model/following is unchanged by report workflow', await authority(page), before);
        const geometry = await page.locator('#morning-desk').evaluate(node => ({ dialog: [node.scrollWidth, node.clientWidth], page: [document.documentElement.scrollWidth, innerWidth], overflowing: [...node.querySelectorAll('*')].filter(child => child.scrollWidth > child.clientWidth + 1 && child.clientWidth > 0).map(child => [child.tagName, child.className, child.scrollWidth, child.clientWidth]).slice(0, 12) }));
        check(name + ': report panel fits phone without horizontal overflow', geometry.dialog[0] <= geometry.dialog[1] + 1 && geometry.page[0] <= geometry.page[1] + 1, JSON.stringify(geometry));
        await privacy(tab, requestStart, name);
      } finally { await tab.context.close(); }
    }
  });

  await run('existing planned source is opened without conversion', async () => {
    const fixture = await producer('priority'), data = JSON.parse(fixture.canonical);
    fixture.now = '2026-10-12T15:00:00Z';
    const row = data.watchlist.top.find(row => row.ticker === 'ZBASE'), reference = row.evidence;
    // Synthetic PRIVATE legacy draft, retaining actual producer terms verbatim.
    // It is not an execution fact or a newly generated public publication.
    const pub = { sha256: sha(fixture.canonical), session: data.run.session, published_at: data.run.published_at, rules_version: data.app.rules_version };
    const plan = { reference: { version: 1, id: reference.id, context_sha256: reference.context_sha256, plan_sha256: reference.planning.output_sha256, pick_sha256: reference.planning.pick_sha256 }, ticker: 'ZBASE', stage: 'setting-up', order: row.plan.order_json,
      timing: Object.fromEntries(['applicable_session', 'opens_at', 'cutoff_at', 'closes_at'].map(key => [key, data.run.timing[key]])), exit_schedule: row.plan.exit_schedule };
    const original = { version: 2, id: pub.sha256 + ':' + reference.id, revision: 1, created_at: '2026-10-10T12:01:00.000Z', updated_at: '2026-10-10T12:01:00.000Z', publication: pub, plan,
      draft: { quantity: 1, cash_cents: 200000, fee_cents: 0 }, report: Object.fromEntries(Object.keys({ ...partial, ...complete }).map(key => [key, null])), report_updated_at: null };
    const seed = JSON.stringify({ version: 2, items: [original] }), tab = await launch(fixture, { seed }), { page } = tab;
    try {
      await reveal(page); await openReport(page, 'ZBASE');
      eq('planned duplicate: research action loads existing planned item rather than blank creation', await page.locator('#morning-handoffs').getAttribute('data-handoff-mode'), 'planned_handoff');
      eq('planned duplicate: action preserves exact legacy bytes with one original draft', [await rawStore(page), (await saved(page)).length], [seed, 1]);
      check('planned duplicate: existing record/correction path is explicit', /already has a private record.*nothing was replaced/.test(await text(page, '[data-handoff-message]')));
      const current = fixture.bundle.rows.find(row => row.ticker === 'ZBASE');
      const result = await page.evaluate(async request => SCStock.handoff.reportResearch(request, { submitted_quantity: '3', filled_quantity: '2' }, null), {
        recordHash: sha(fixture.reader), projected: true, publication: fixture.receipt.publication, cohort: { sha256: fixture.receipt.bundle.sha256, bytes: fixture.receipt.bundle.bytes, generated_at: fixture.receipt.timing.generated_at, policy_id: fixture.receipt.policy.id }, ticker: 'ZBASE', evidence: current.evidence
      });
      eq('planned duplicate: model creation refuses shared original ID without overwrite', [result.ok, result.existingId, await rawStore(page)], [false, original.id, seed]);
      await set(page, { submitted_quantity: '3', filled_quantity: '2', average_price: '120.01' }); await save(page);
      const corrected = (await saved(page))[0];
      eq('planned duplicate: explicit correction preserves original planned terms', [corrected.kind, corrected.plan, corrected.draft, corrected.report.filled_quantity], ['planned_handoff', original.plan, original.draft, 2]);
      eq('planned duplicate: no uncaught errors', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });

  await run('admitted origin after cutoff', async () => {
    const fixture = await producer('priority'); fixture.now = '2026-10-12T15:00:00Z';
    const tab = await launch(fixture), { page } = tab;
    try {
      await reveal(page); const start = tab.requests.length;
      const row = fixture.bundle.rows.find(row => row.ticker === 'ZBASE');
      eq('admitted origin: genuine producer retains baseline admission', row.baseline.admitted, true);
      await openReport(page, 'ZBASE');
      check('admitted origin: original admission is visible but adds no entry permission', /Original production baseline: admitted.*grants no entry permission/.test(await text(page, '[data-handoff-research-source]')));
      eq('admitted origin: even after cutoff opening stays blank', await field(page, 'filled_quantity').inputValue(), '');
      await set(page, { submitted_quantity: '3', filled_quantity: '2', average_price: '120.01', filled_at: '2026-10-12T14:10:00Z' }); await save(page);
      const item = (await saved(page))[0];
      check('admitted origin: actual fill after cutoff remains recordable without prior draft', item?.kind === 'independent_research' && item.source.baseline_admitted === true && item.report.filled_quantity === 2);
      eq('admitted origin: execution reporting never enables order copy', await page.locator('[data-handoff-copy]').isDisabled(), true);
      eq('admitted origin: no personal draft fields are manufactured', item && ['plan', 'draft', 'order'].filter(key => key in item), []);
      await privacy(tab, start, 'admitted origin');
    } finally { await tab.context.close(); }
  });

  await run('replacement and dated corrections', async () => {
    const original = await producer('priority'), replacement = await producer('red'), tab = await launch(original), { page } = tab;
    try {
      await reveal(page);
      await page.locator('.ss-morning__prep > summary').click(); await page.locator('#morning-cash').fill('1543.21');
      await page.evaluate(() => { window.__oldReportAction = document.querySelector('[data-stop-report="COIL"]'); });
      await openReport(page, 'COIL'); await set(page, { submitted_quantity: '5', filled_quantity: '4', average_price: '111.12' });
      await field(page, 'average_price').focus();
      await page.evaluate(() => { window.__replacementInput = document.querySelector('[data-handoff-field="average_price"]'); window.__replacementCash = document.getElementById('morning-cash'); });
      tab.state.fixture = replacement;
      await page.locator('#check-updates').evaluate(node => node.click());
      await page.waitForFunction(hash => SCStock.observations.facts().recordHash === hash && !SCStock.observations.facts().pending, sha(replacement.reader));
      eq('replacement: publication update preserves unsaved exact field node/value/focus', await field(page, 'average_price').evaluate(node => [node === window.__replacementInput, node.value, document.activeElement === node]), [true, '111.12', true]);
      eq('replacement: publication update preserves local settled cash node and value', await page.locator('#morning-cash').evaluate(node => [node === window.__replacementCash, node.value]), [true, '1543.21']);
      await save(page);
      eq('replacement: stale captured source refuses creation despite same ticker', await rawStore(page), null);
      check('replacement: explicit refusal explains another/unverified publication', /another|unverified|changed/i.test(await text(page, '[data-handoff-message]')));
      await page.locator('[data-handoff-cancel]').click(); await reveal(page);
      eq('replacement: actual red producer still contains original same ticker', replacement.bundle.rows.some(row => row.ticker === 'COIL'), true);
      await page.evaluate(() => window.__oldReportAction.click());
      eq('replacement: detached old same-ticker action cannot create current editor', await page.locator('#morning-handoffs').getAttribute('data-handoff-mode'), 'planned_handoff');
      eq('replacement: held old action never writes a private item', await rawStore(page), null);
      await openReport(page, 'COIL'); await set(page, { submitted_quantity: '5', filled_quantity: '4', average_price: '111.12' }); await save(page);
      const item = (await saved(page))[0], source = JSON.stringify(item.source);
      eq('replacement: newly explicit report binds only exact replacement evidence', item.source.evidence, replacement.bundle.rows.find(row => row.ticker === 'COIL').evidence);
      tab.state.fixture = original;
      await page.locator('#check-updates').evaluate(node => node.click());
      await page.waitForFunction(hash => SCStock.observations.facts().recordHash === hash && !SCStock.observations.facts().pending, sha(original.reader));
      await page.evaluate(() => { SCStock.now = '2026-10-13T16:00:00Z'; window.__reportClock = Date.parse(SCStock.now); SCStock.reclock(); });
      await field(page, 'average_price').fill('112.22'); await save(page);
      eq('replacement: later corrections retain original source after expiry and replacement', [(await saved(page))[0].report.average_price, JSON.stringify((await saved(page))[0].source)], ['112.22', source]);
      eq('replacement: saved report remains report-only after original/current swap', await page.locator('[data-handoff-copy]').isDisabled(), true);
      eq('replacement: no uncaught errors', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });

  await run('CAS and storage recovery', async () => {
    const tab = await launch(await producer('current')), { page, context } = tab;
    try {
      await reveal(page); await openReport(page, 'KE'); await set(page, partial); await save(page);
      const item = (await saved(page))[0];
      await field(page, 'average_price').fill('30.123456'); await field(page, 'average_price').focus();
      await page.evaluate(() => { window.__casDirty = document.querySelector('[data-handoff-field="average_price"]'); });
      const peer = await context.newPage();
      await peer.goto(base + '/docs/index.html'); await peer.waitForFunction(() => SCStock.handoff?.list().length === 1);
      const peerResult = await peer.evaluate(async id => { const item = SCStock.handoff.find(id); return SCStock.handoff.report(id, { ...item.report, average_price: '32.12' }, item.revision); }, item.id);
      check('CAS: actual second browser view saves the current revision', peerResult.ok);
      await save(page);
      eq('CAS: stale UI correction cannot overwrite other tab', (await saved(page))[0].report.average_price, '32.12');
      eq('CAS: conflict preserves exact dirty field node and entered value', await field(page, 'average_price').evaluate(node => [node === window.__casDirty, node.value]), [true, '30.123456']);
      check('CAS: conflict explicitly offers loading saved report', /changed|another|current/i.test(await text(page, '[data-handoff-message]')));
      await page.locator('[data-handoff-reload]').click();
      eq('CAS: explicit reload selects winning actual report', await field(page, 'average_price').inputValue(), '32.12');
      await peer.close();
      const prior = await rawStore(page);
      await page.evaluate(key => { const original = Storage.prototype.setItem; window.__rejectReportWrite = true; Storage.prototype.setItem = function (name, value) { if (name === key && window.__rejectReportWrite) throw new DOMException('Synthetic private quota control', 'QuotaExceededError'); return original.call(this, name, value); }; }, KEY);
      await field(page, 'average_price').fill('29.99'); await save(page);
      eq('storage: quota refusal preserves original bytes and input', [await rawStore(page), await field(page, 'average_price').inputValue()], [prior, '29.99']);
      const recovery = await page.evaluate(() => SCStock.handoff.recovery());
      eq('storage: recovery preserves exact prior bytes', recovery.prior, prior);
      check('storage: recovery contains proposed actual correction without source loss', recovery.proposed && JSON.parse(recovery.proposed).items[0].report.average_price === '29.99' && JSON.stringify(JSON.parse(recovery.proposed).items[0].source) === JSON.stringify(item.source));
      eq('storage: explicit private recovery download is offered', await page.locator('[data-handoff-recovery]').isVisible(), true);
      await page.evaluate(() => { window.__rejectReportWrite = false; });
      await save(page);
      eq('storage: deliberate retry saves retained actual correction', (await saved(page))[0].report.average_price, '29.99');
      eq('storage: no uncaught errors', Array.from(tab.errors), []);
    } finally { await context.close(); }
  });

  await run('legacy read-only migration', async () => {
    const module = await readFile(path.join(ROOT, 'tools/handoff_model_cases.mjs'), 'utf8');
    const match = module.match(/^const LEGACY_RAW = ("(?:[^"\\]|\\.)*");$/m);
    check('legacy: original model-produced synthetic v1 control is present', !!match);
    if (!match) return;
    const original = JSON.parse(match[1]);
    for (const version of [1, 2]) {
      let raw = original;
      if (version === 2) { const data = JSON.parse(original); data.version = 2; data.items.forEach(item => { item.version = 2; Object.assign(item.report, { average_exit_price: null, entry_fees: null, exit_fees: null }); }); raw = JSON.stringify(data); }
      const tab = await launch(await producer('current'), { seed: raw }), { page } = tab;
      try {
        await page.locator('#morning-open').click(); await page.locator('#morning-handoffs > summary').click();
        eq('legacy v' + version + ': opening preserves exact original storage bytes', await rawStore(page), raw);
        eq('legacy v' + version + ': in-memory normalization adds only planned kind/version', (await saved(page)).map(item => [item.version, item.kind, item.plan.ticker, item.draft.quantity]), [[3, 'planned_handoff', 'COIL', 2]]);
        eq('legacy v' + version + ': unknown actual costs remain blank', [await field(page, 'entry_fees').inputValue(), await field(page, 'exit_fees').inputValue()], ['', '']);
        const old = JSON.parse(raw).items[0];
        if (!await page.locator('[data-handoff-report]').evaluate(node => node.open)) await page.locator('[data-handoff-report] > summary').click();
        await field(page, 'entry_fees').fill('0.001'); await save(page);
        eq('legacy v' + version + ': invalid correction does not trigger migration', await rawStore(page), raw);
        await field(page, 'entry_fees').fill('0.00'); await save(page);
        const upgraded = JSON.parse(await rawStore(page));
        eq('legacy v' + version + ': explicit valid save writes v3 planned form', [upgraded.version, upgraded.items[0].version, upgraded.items[0].kind], [3, 3, 'planned_handoff']);
        eq('legacy v' + version + ': explicit migration preserves original terms and private draft', [upgraded.items[0].plan, upgraded.items[0].draft, upgraded.items[0].publication], [old.plan, old.draft, old.publication]);
        eq('legacy v' + version + ': no uncaught errors', Array.from(tab.errors), []);
      } finally { await tab.context.close(); }
    }
  });

  await run('unknown private version recovery', async () => {
    const raw = JSON.stringify({ version: 99, items: [{ private_control: 'SYNTHETIC unknown future record' }] });
    const tab = await launch(await producer('current'), { seed: raw }), { page } = tab;
    try {
      await reveal(page); await openReport(page, 'KE');
      eq('unknown version: opening never replaces or silently evicts unknown records', await rawStore(page), raw);
      eq('unknown version: creation cannot write over unreadable original storage', await page.locator('[data-handoff-save]').isDisabled(), true);
      check('unknown version: unavailable storage is not described as no holdings', /unavailable|unreadable|another version/.test(await text(page, '[data-handoff-storage]')) && /not a claim that you hold no position/.test(await text(page, '[data-handoff-empty]')));
      eq('unknown version: exact raw recovery copy remains offered', [await page.evaluate(() => SCStock.handoff.recovery().prior), await page.locator('[data-handoff-recovery]').isVisible()], [raw, true]);
      eq('unknown version: no uncaught errors', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });
}
