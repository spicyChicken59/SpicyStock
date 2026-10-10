/* Offline genuine producer journals; actual broker facts below are synthetic,
   entered only in fresh private browser storage. No live profile or provider. */
import { readFile, mkdir } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const KEY = 'spicystock:handoff:v1';
const sha = raw => createHash('sha256').update(raw).digest('hex');
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const records = page => page.evaluate(() => SCStock.handoff.list());
const rawStore = page => page.evaluate(key => localStorage.getItem(key), KEY);
const set = async (page, values) => { for (const [key, value] of Object.entries(values)) await field(page, key).fill(value); };
const save = async page => { await page.locator('[data-handoff-save]').click(); await page.waitForFunction(() => !document.querySelector('[data-handoff-save]').disabled); };

async function producer(name) {
  const stem = path.join(ROOT, 'tests/fixtures/research-outcomes', name);
  const [canonical, reader, receiptRaw, bundleRaw] = await Promise.all([
    readFile(stem + '-publication.json.gz').then(gunzipSync), readFile(stem + '-reader.json.gz').then(gunzipSync),
    readFile(stem + '-receipt.json'), readFile(stem + '-bundle.json')
  ]);
  const receipt = JSON.parse(receiptRaw), bundle = JSON.parse(bundleRaw);
  return { name, canonical, reader, receiptRaw, bundleRaw, receipt, bundle,
    sources: bundle.cohorts.map(entry => JSON.parse(entry.source.raw)), now: new Date(Date.parse(receipt.generated_at) + 60000).toISOString() };
}
function original(fixture, index, ticker) {
  const entry = fixture.bundle.cohorts[index], source = fixture.sources[index], row = source.rows.find(row => row.ticker === ticker);
  return { ticker, stage: 'setting-up', publication: source.publication,
    cohort: { sha256: entry.source.sha256, bytes: entry.source.bytes, generated_at: source.timing.generated_at, policy_id: source.policy.id },
    evidence: row.evidence, baseline_admitted: row.baseline.admitted };
}
async function requestFor(page, fixture, ticker, index = 0) {
  const hashes = await page.evaluate(() => { const f = SCStock.observations.facts(); return { recordHash: f.recordHash, projected: f.projected }; });
  const source = original(fixture, index, ticker);
  return { origin: 'retained_journal', ...hashes, publication: fixture.receipt.publication,
    journal: { sha256: fixture.receipt.bundle.sha256, bytes: fixture.receipt.bundle.bytes, generated_at: fixture.receipt.generated_at, cohort_set_sha256: fixture.receipt.cohort_set_sha256 },
    cohort: source.cohort, ticker, evidence: source.evidence };
}
const row = (page, fixture, ticker, index = 0) => page.locator('[data-outcome-cohort="' + fixture.bundle.cohorts[index].source.sha256 + '"] [data-outcome-row="' + ticker + '"]');
const report = async (page, fixture, ticker, index = 0) => { await row(page, fixture, ticker, index).locator('[data-outcome-report]').click(); };
const reveal = async page => {
  if (!await page.locator('#morning-desk').evaluate(node => node.open)) await page.locator('#morning-open').click();
  if (!await page.locator('[data-research-outcomes]').evaluate(node => node.open)) await page.locator('[data-research-outcomes] > summary').click();
  await page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.researchOutcomes.status().state));
};

export async function checkJournalReports({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- journal reports: original historical identity, synthetic actual facts, no model or entry authority');
  const run = async (name, fn) => { try { await fn(); } catch (error) { check(name + ': workflow completes', false, error.stack); } };
  const launch = async (fixture, { width = 1280, seed = null, unavailable = false } = {}) => {
    const requests = [], responses = [], transport = { fixture, unavailable, hold: false, release: null };
    const tab = await open(browser, base, null, fixture.now, width, {
      theme: width === 390 ? 'light' : 'dark', lens: 'all', reducedMotion: 'reduce', beforeLoad: async (page, context) => {
        page.setDefaultTimeout(5000);
        await context.addInitScript(({ now, seed, key }) => {
          const NativeDate = Date; window.__journalClock = Date.parse(now);
          window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [window.__journalClock])); } static now() { return window.__journalClock; } };
          if (seed !== null) localStorage.setItem(key, seed);
          const put = Storage.prototype.setItem; window.__journalWrites = 0; window.__journalCopies = 0;
          Storage.prototype.setItem = function (name, raw) { if (name === key) window.__journalWrites++; return put.call(this, name, raw); };
          Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { window.__journalCopies++; } } });
        }, { now: fixture.now, seed, key: KEY });
        context.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
        context.on('response', response => responses.push({ url: response.url(), status: response.status() }));
        await context.route('**/*', async route => {
          const url = new URL(route.request().url()), f = transport.fixture;
          if (url.origin !== base) { await route.fulfill({ contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'application/json', body: url.hostname === 'fonts.googleapis.com' ? '' : '{}' }); return; }
          if (url.pathname === '/docs/reader.json') { await route.fulfill({ status: transport.unavailable ? 503 : 200, contentType: 'application/json', body: f.reader }); return; }
          if (url.pathname === '/docs/morning.json') { await route.fulfill({ contentType: 'application/json', body: '{}' }); return; }
          if (url.pathname === '/docs/research-outcomes.json') {
            if (transport.hold) await new Promise(resolve => { transport.release = resolve; });
            await route.fulfill({ contentType: 'application/json', body: f.receiptRaw }); return;
          }
          if (url.pathname.startsWith('/docs/research-outcomes/')) { await route.fulfill({ contentType: 'application/json', body: f.bundleRaw }); return; }
          await route.continue();
        });
      }
    });
    if (!unavailable) await tab.page.waitForFunction(() => SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    return { ...tab, requests, responses, transport };
  };
  const capture = async (page, name, selector) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true }); await page.locator(selector).scrollIntoViewIfNeeded();
    await page.locator(selector).screenshot({ path: path.join(shotsDir, name + '.png') });
  };
  const authority = page => page.evaluate(() => [JSON.stringify(SCStock.data), JSON.stringify(SCStock.model), localStorage.getItem('spicystock:following:v1')]);
  const privacy = async (tab, start, name) => {
    eq(name + ': actual private reporting sends no request', tab.requests.slice(start), []);
    eq(name + ': no order can be copied', await tab.page.evaluate(() => window.__journalCopies), 0);
    const errors = Array.from(tab.errors);
    if (tab.transport.unavailable) {
      // Native preflight intentionally cancels this one failed body. Pair its
      // exact URL/status first; no generic request/error exemption is added.
      const url = base + '/docs/reader.json';
      eq(name + ': explicit startup refusal is exactly the served 503', tab.responses.filter(r => r.url === url), [{ url, status: 503 }]);
      for (const expected of ['console: Failed to load resource: the server responded with a status of 503 (Service Unavailable)', 'request failed: ' + url + ' net::ERR_ABORTED']) {
        const index = errors.indexOf(expected); if (index >= 0) errors.splice(index, 1);
      }
    }
    eq(name + ': no error beyond the explicit status-paired startup refusal', errors, []);
  };
  const actual = { submitted_quantity: '5', filled_quantity: '3', average_price: '31.234567', filled_at: '2026-10-12T14:01:00Z', submitted_at: '2026-10-12T14:00:00Z' };
  let persisted = null;
  for (const width of [390, 1280]) await run('old original report/' + width, async () => {
    const fixture = await producer('observed'), tab = await launch(fixture, { width }), { page } = tab, name = 'old original/' + width;
    try {
      eq(name + ': journal is closed and causes no lazy request at startup', tab.requests.filter(r => /\/research-outcomes(?:\.json|\/)/.test(r.url)), []);
      await reveal(page);
      eq(name + ': actual canonical and compact-reader bytes bind the journal', await page.evaluate(() => [SCStock.observations.facts().canonicalHash, SCStock.observations.facts().recordHash]), [sha(fixture.canonical), sha(fixture.reader)]);
      eq(name + ': producer resolves a model, not a personal trade', [(await records(page)).length, fixture.bundle.cohorts[0].rows.find(r => r.ticker === 'COIL').model.status], [0, 'resolved']);
      eq(name + ': every verified original row offers reporting independently of model status', await page.locator('[data-outcome-report]').count(), fixture.sources[0].rows.length);
      const before = await authority(page), start = tab.requests.length;
      await capture(page, 'journal-original-row-' + width, '[data-outcome-cohort="' + fixture.bundle.cohorts[0].source.sha256 + '"] [data-outcome-row="COIL"]');
      await row(page, fixture, 'COIL').locator('[data-outcome-report]').focus(); await page.keyboard.press('Enter');
      eq(name + ': keyboard action focuses blank private heading', await page.evaluate(() => document.activeElement.id), 'handoff-title');
      eq(name + ': no model quantity, price, time, exit, protection or fee defaults', await page.locator('[data-handoff-field]').evaluateAll(nodes => nodes.map(node => node.value)), Array(14).fill(''));
      eq(name + ': opening creates neither storage nor write', [await rawStore(page), await page.evaluate(() => window.__journalWrites)], [null, 0]);
      const expected = original(fixture, 0, 'COIL');
      check(name + ': original publication is genuinely older than active journal', expected.publication.data_sha256 !== fixture.receipt.publication.data_sha256);
      eq(name + ': visible source remains original not active observation publication', await page.locator('[data-handoff-research-digests]').evaluate((node, expected) => node.textContent.includes(expected), expected.publication.data_sha256), true);
      eq(name + ': raw reference disclosure starts closed', await page.locator('[data-handoff-research-references]').evaluate(node => node.open), false);
      await capture(page, 'journal-blank-' + width, '#morning-desk');
      await save(page); eq(name + ': blank broker facts cannot save', await rawStore(page), null);
      await set(page, { submitted_quantity: '1', filled_quantity: '0' }); await save(page);
      eq(name + ': explicit zero fill is not an executed trade', await rawStore(page), null);
      await set(page, actual); await save(page);
      const item = (await records(page))[0]; check(name + ': explicit positive fill creates one independent private report', !!item && item.kind === 'independent_research');
      if (!item) return;
      eq(name + ': identity uses original publication and evidence, not active journal or ticker', item.id, expected.publication.data_sha256 + ':' + expected.evidence.id);
      eq(name + ': exact original source and baseline admission survive', item.source, expected);
      eq(name + ': hypothetical one-share model never caps actual three-share broker fill', [fixture.sources[0].rows.find(r => r.ticker === 'COIL').research.shares, item.report.filled_quantity], [1, 3]);
      eq(name + ': actual facts remain unknown until entered', [item.report.cancelled_quantity, item.report.exited_quantity, item.report.entry_fees, item.report.exit_fees], [null, null, null, null]);
      eq(name + ': report-only item has no entry draft, cash arithmetic or readback', await page.evaluate(id => { const item = SCStock.handoff.find(id), s = SCStock.handoff.summary(item); return [item.plan || null, item.draft || null, s.calculation, SCStock.handoff.readback(item), SCStock.handoff.copy(id).ok]; }, item.id), [null, null, null, '', false]);
      const prior = await rawStore(page);
      await set(page, { cancelled_quantity: '3' }); await save(page);
      eq(name + ': actual fill plus cancellation conserves submitted total', await rawStore(page), prior);
      await set(page, { cancelled_quantity: '2', cancelled_at: '2026-10-12T14:02:00Z', exited_quantity: '3', average_exit_price: '32.345678', exited_at: '2026-10-12T16:00:00Z', entry_fees: '0.11', exit_fees: '0.22' }); await save(page);
      eq(name + ': result uses actual three-share prices/costs rather than model R', await page.evaluate(id => { const r = SCStock.handoff.summary(SCStock.handoff.find(id)).completed_result; return [r.net_microusd, r.net_display]; }, item.id), ['3003333', '$3.00']);
      await field(page, 'exit_fees').fill(''); await save(page);
      eq(name + ': an unknown actual fee removes completed amounts without substituting model costs', await page.evaluate(id => SCStock.handoff.summary(SCStock.handoff.find(id)).completed_result.state, item.id), 'incomplete');
      const savedRaw = await rawStore(page); persisted = savedRaw;
      await report(page, fixture, 'COIL');
      eq(name + ': repeated original action preserves record/source with no duplicate', [await rawStore(page), (await records(page)).length], [savedRaw, 1]);
      await field(page, 'average_price').fill('30.125'); await field(page, 'average_price').focus();
      await page.evaluate(() => window.__journalDirty = document.querySelector('[data-handoff-field="average_price"]'));
      await report(page, fixture, 'RONE');
      eq(name + ': another original cannot erase dirty input node/value', await field(page, 'average_price').evaluate(node => [node === window.__journalDirty, node.value]), [true, '30.125']);
      check(name + ': dirty switch is explained beside the requested original', /unsaved|kept|discard/i.test(await row(page, fixture, 'RONE').locator('[data-outcome-report-status]').textContent()));
      await page.locator('#morning-close').click(); await page.locator('#morning-open').click();
      eq(name + ': ordinary close/reopen keeps exact dirty private input', await field(page, 'average_price').evaluate(node => [node === window.__journalDirty, node.value]), [true, '30.125']);
      eq(name + ': private reports cannot mutate public data/model/following', await authority(page), before);
      check(name + ': phone and desktop have no horizontal overflow', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth + 1));
      await capture(page, 'journal-saved-' + width, '#morning-desk'); await privacy(tab, start, name);
    } finally { await tab.context.close(); }
  });

  for (const [variant, ticker, status] of [['missing', 'COIL', 'missing'], ['not-filled', 'COIL', 'not_filled'], ['basis-conflict', 'COIL', 'basis_conflict'], ['observed', 'ZBASE', 'excluded']]) await run('model distinction/' + variant, async () => {
    const fixture = await producer(variant), tab = await launch(fixture), { page } = tab;
    try {
      await reveal(page); const start = tab.requests.length;
      eq(variant + ': genuine conditional model state is explicit', fixture.bundle.cohorts[0].rows.find(r => r.ticker === ticker).model.status, status);
      await report(page, fixture, ticker);
      eq(variant + ': model state never infers a broker fill', await field(page, 'filled_quantity').inputValue(), '');
      await set(page, { submitted_quantity: '2', filled_quantity: '1' }); await save(page);
      const item = (await records(page))[0]; check(variant + ': actual independently reported fill is allowed for a verified original', !!item);
      if (item) eq(variant + ': true original baseline admission is retained, without an order', [item.source.baseline_admitted, item.plan || null], [original(fixture, 0, ticker).baseline_admitted, null]);
      await privacy(tab, start, variant);
    } finally { await tab.context.close(); }
  });

  await run('repeated cohort identity', async () => {
    const fixture = await producer('cohort-revisions'), tab = await launch(fixture), { page } = tab;
    try {
      await reveal(page); const start = tab.requests.length;
      check('revision: genuine producer retains two distinct cohort digests', fixture.bundle.cohorts.length === 2 && fixture.bundle.cohorts[0].source.sha256 !== fixture.bundle.cohorts[1].source.sha256);
      await report(page, fixture, 'COIL', 0); await set(page, { submitted_quantity: '2', filled_quantity: '1' }); await save(page);
      const item = (await records(page))[0], prior = await rawStore(page);
      await report(page, fixture, 'COIL', 1);
      eq('revision: same original from later cohort opens saved report without replacement', [await rawStore(page), (await records(page)).length], [prior, 1]);
      eq('revision: selected report keeps first original cohort rather than revision identity', (await records(page))[0].source, item.source);
      await field(page, 'average_price').fill('22.123456'); await save(page);
      eq('revision: explicit correction preserves original identity/source', [(await records(page))[0].id, (await records(page))[0].source, (await records(page))[0].report.average_price], [item.id, item.source, '22.123456']);
      await privacy(tab, start, 'revision');
    } finally { await tab.context.close(); }
  });

  await run('exact journal reference and reload state', async () => {
    const fixture = await producer('observed'), tab = await launch(fixture), { page } = tab;
    try {
      await reveal(page); const request = await requestFor(page, fixture, 'COIL');
      const source = await page.evaluate(request => SCStock.handoff.inspectResearch(request), request);
      eq('reference: exact loaded journal reconstructs original source', source, { ok: true, source: original(fixture, 0, 'COIL') });
      const wrong = [
        ['active publication', r => { r.publication.data_sha256 = '0'.repeat(64); }],
        ['journal snapshot', r => { r.journal.sha256 = '0'.repeat(64); }],
        ['journal clock', r => { r.journal.generated_at = '2026-10-12T23:00:01Z'; }],
        ['original clock', r => { r.cohort.generated_at = '2026-10-10T12:00:01Z'; }],
        ['original evidence', r => { r.evidence.source_sha256 = '0'.repeat(64); }],
        ['unsupported discriminator', r => { r.origin = 'unknown'; }],
        ['null discriminator', r => { r.origin = null; }]
      ];
      for (const [name, change] of wrong) {
        const changed = structuredClone(request); change(changed);
        eq('reference ' + name + ': mismatched lookup refuses without source substitution', await page.evaluate(request => SCStock.handoff.inspectResearch(request).ok, changed), false);
      }
      const currentOnly = structuredClone(request); delete currentOnly.origin; delete currentOnly.journal;
      eq('reference: current-comparison path never falls back to historical journal', await page.evaluate(request => SCStock.handoff.inspectResearch(request).ok, currentOnly), false);
      const before = await rawStore(page); tab.transport.hold = true;
      await page.evaluate(() => { window.__heldJournalReport = document.querySelector('[data-outcome-report="COIL"]'); SCStock.researchOutcomes.reload(); });
      await page.waitForFunction(() => SCStock.researchOutcomes.status().state === 'loading');
      eq('loading: old valid source cannot authorize a report during journal revalidation', await page.evaluate(request => SCStock.handoff.inspectResearch(request).ok, request), false);
      await row(page, fixture, 'COIL').locator('[data-outcome-report]').click();
      check('loading: visible blocked row gives explicit source-change guidance', /no longer|verified|reload/i.test(await row(page, fixture, 'COIL').locator('[data-outcome-report-status]').textContent()));
      await page.evaluate(() => window.__heldJournalReport.click());
      eq('loading: detached old callback cannot open transient broker editor', await page.locator('#morning-handoffs').getAttribute('data-handoff-mode'), 'planned_handoff');
      eq('loading: callback writes no record', await rawStore(page), before);
      for (let attempt = 0; attempt < 250 && !tab.transport.release; attempt++) await new Promise(resolve => setTimeout(resolve, 20));
      if (!tab.transport.release) throw Error('Expected held journal receipt request did not arrive');
      tab.transport.hold = false; tab.transport.release();
      await page.waitForFunction(() => SCStock.researchOutcomes.status().state === 'loaded');
      eq('loading: completed revalidation restores only exact lookup', await page.evaluate(request => SCStock.handoff.inspectResearch(request).ok, request), true);
      eq('reference controls: no private writes or copied orders', await page.evaluate(() => [window.__journalWrites, window.__journalCopies]), [0, 0]);
      eq('reference controls: no browser errors', Array.from(tab.errors), []);
    } finally { if (tab.transport.release) tab.transport.release(); await tab.context.close(); }
  });

  await run('same original explicit verified reopen', async () => {
    const first = await producer('synthetic-pending'), next = await producer('cohort-revisions'); first.now = next.now;
    const tab = await launch(first), { page } = tab;
    try {
      await reveal(page); await report(page, first, 'COIL'); await set(page, { submitted_quantity: '2', filled_quantity: '1', average_price: '44.56789' });
      await field(page, 'average_price').focus(); await page.evaluate(() => window.__reopenNode = document.querySelector('[data-handoff-field="average_price"]'));
      eq('reopen: genuine journal changes active snapshot without changing canonical', sha(first.canonical), sha(next.canonical));
      tab.transport.fixture = next; await page.evaluate(() => SCStock.researchOutcomes.reload());
      await page.waitForFunction(() => SCStock.researchOutcomes.status().state === 'loaded');
      await save(page); eq('reopen: old snapshot request cannot silently authorize new first save', await rawStore(page), null);
      eq('reopen: stale refusal keeps exact dirty broker fields', await field(page, 'average_price').evaluate(node => [node === window.__reopenNode, node.value]), [true, '44.56789']);
      await report(page, next, 'COIL', 0);
      eq('reopen: explicit current row renews only lookup, retaining dirty input node/value', await field(page, 'average_price').evaluate(node => [node === window.__reopenNode, node.value]), [true, '44.56789']);
      await save(page); const item = (await records(page))[0];
      check('reopen: renewed verified journal reference can now save actual facts', !!item && item.report.average_price === '44.56789');
      if (item) eq('reopen: original source did not become active journal publication', item.source, original(first, 0, 'COIL'));
      eq('reopen: no copied order', await page.evaluate(() => window.__journalCopies), 0);
      eq('reopen: no uncaught browser errors', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });

  await run('source-less private recovery', async () => {
    check('recovery: earlier explicit synthetic private report is available', !!persisted); if (!persisted) return;
    const fixture = await producer('observed'), tab = await launch(fixture, { seed: persisted, unavailable: true }), { page } = tab;
    try {
      await page.locator('#morning-open').click(); await page.locator('#morning-handoffs > summary').click();
      const item = (await records(page))[0], before = await rawStore(page), source = JSON.stringify(item.source), start = tab.requests.length;
      eq('recovery: absent publication cannot hide original private report or auto-migrate it', [item.kind, await rawStore(page), await page.evaluate(() => SCStock.data)], ['independent_research', before, null]);
      const exported = await page.evaluate(() => SCStock.handoff.exportBackup()); eq('recovery: backup preserves exact old-source report bytes', exported.raw, before);
      if (!await page.locator('[data-handoff-report]').evaluate(node => node.open)) await page.locator('[data-handoff-report] > summary').click();
      await field(page, 'average_price').fill('39.876543'); await save(page);
      eq('recovery: actual correction stays possible with no active public source', [(await records(page))[0].report.average_price, JSON.stringify((await records(page))[0].source)], ['39.876543', source]);
      eq('recovery: source-less historical record cannot copy or prepare an entry', await page.evaluate(id => [SCStock.handoff.copy(id).ok, SCStock.handoff.availability(SCStock.handoff.find(id)).ok], item.id), [false, false]);
      await capture(page, 'journal-private-recovery', '#morning-desk'); await privacy(tab, start, 'recovery');
    } finally { await tab.context.close(); }
  });
}
