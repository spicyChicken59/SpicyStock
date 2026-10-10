#!/usr/bin/env node
/* Recorded-decision inspection over retained raw bytes and producer fixtures.
   Private reports and malformed transport copies below are explicit offline
   controls. No market/broker request, public data rewrite or real profile. */
import { createServer } from 'node:http';
import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = path.resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const option = name => args.includes(name) ? args[args.indexOf(name) + 1] : null;
const reportPath = option('--report');
let shotsDir = option('--shots');
const selected = option('--only')?.split(',');
const run = name => !selected || selected.includes(name);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const results = [], cases = [];
let check = (name, pass, detail) => {
  results.push({ name, pass: !!pass, ...(!pass ? { detail } : {}) });
  if (!pass) console.log('FAIL ' + name + (detail === undefined ? '' : ': ' + JSON.stringify(detail)));
};
const eq = (name, got, expected) => check(name, JSON.stringify(got) === JSON.stringify(expected), { got, expected });
const read = name => readFile(path.join(ROOT, name));
const decoded = async name => name.endsWith('.gz') ? gunzipSync(await read(name)) : read(name);
const text = (page, selector) => page.locator(selector).count().then(count => count ? page.locator(selector).first().textContent() : '');

async function producer(name) {
  const stem = 'tests/fixtures/stop-research/' + name;
  const [canonical, reader, receiptRaw, bundle] = await Promise.all([
    decoded(stem + '-publication.json.gz'), decoded(stem + '-reader.json.gz'),
    read(stem + '-receipt.json'), read(stem + '-bundle.json')
  ]);
  const receipt = JSON.parse(receiptRaw);
  return { name, canonical, reader, receiptRaw, receipt, bundle, now: new Date(Date.parse(receipt.timing.generated_at) + 60000).toISOString() };
}
async function retained() {
  // This generator's current variant retains the complete actual Oct 9 source,
  // not a new synthetic scan. Keep CI independent of tomorrow's docs/data.json.
  return { ...await producer('current'), name: 'actual-retained' };
}
async function cashFixture() {
  const [canonical, morning] = await Promise.all(['publication.json', 'observed.json'].map(name => read('tests/fixtures/cash-preview/' + name)));
  return { name: 'producer-cash', canonical, reader: null, morning, now: '2026-09-11T13:35:00Z' };
}
async function playwright() {
  try { return await import('playwright'); } catch (initial) {
    for (const dir of (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean)) {
      try { return await import(pathToFileURL(path.join(dir, 'playwright/index.mjs')).href); } catch { /* try next installed package */ }
    }
    throw initial;
  }
}
async function server() {
  const overrides = { '/docs/app.js': process.env.SCSTOCK_APP, '/docs/app-morning.js': process.env.SCSTOCK_MORNING,
    '/docs/app-stop-research.js': process.env.SCSTOCK_STOP_RESEARCH };
  const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
  const host = createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://local');
      let file = path.resolve(ROOT, '.' + decodeURIComponent(url.pathname));
      if (!file.startsWith(ROOT + path.sep)) throw Error('outside test root');
      if ((await stat(file)).isDirectory()) file = path.join(file, 'index.html');
      const raw = await readFile(overrides[url.pathname] || file);
      response.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      response.end(raw);
    } catch { response.writeHead(404); response.end('not found'); }
  });
  await new Promise(resolve => host.listen(0, '127.0.0.1', resolve));
  return { host, base: 'http://127.0.0.1:' + host.address().port };
}
const authority = page => page.evaluate(() => ({ data: JSON.stringify(SCStock.data), model: JSON.stringify(SCStock.model),
  storage: JSON.stringify(Object.fromEntries(Object.keys(localStorage).sort().map(key => [key, localStorage.getItem(key)]))),
  morning: JSON.stringify(SCStock.observations.facts()),
  orders: [...document.querySelectorAll('[data-copy], [data-order], [data-handoff-prepare]')].map(node => [node.dataset.copy, node.dataset.order, node.disabled]) }));
const researchSelector = '[data-stop-inspect]';
const topRows = data => data.watchlist?.top || [];
const identity = (fixture, row, facts) => ({ kind: 'anticipation', ticker: row.ticker,
  publication: fixture.receipt?.publication || JSON.parse(fixture.morning).publication,
  recordHash: facts.recordHash, projected: facts.projected,
  evidence: { id: row.evidence.id, plan_sha256: row.evidence.planning.output_sha256, source_sha256: row.evidence.source.sha256 } });

async function launch(browser, base, fixture, { width = 1280, theme = 'dark', canonical = false } = {}) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce' });
  const page = await context.newPage(), requests = [], errors = [], state = { fixture };
  page.setDefaultTimeout(5000);
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== base) {
      // Fonts and optional run-log calls cannot contact the network in this suite.
      await route.fulfill({ status: 200, contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'application/json', body: url.hostname === 'fonts.googleapis.com' ? '' : '{}' });
      return;
    }
    const f = state.fixture;
    if (url.pathname === '/docs/reader.json' || url.pathname === '/decision-publication.json') {
      await route.fulfill({ contentType: 'application/json', body: url.pathname === '/decision-publication.json' ? f.canonical : f.reader }); return;
    }
    if (url.pathname === '/docs/morning.json') { await route.fulfill({ contentType: 'application/json', body: f.morning || '{}' }); return; }
    if (url.pathname === '/docs/stop-research.json' && f.receiptRaw) { await route.fulfill({ contentType: 'application/json', body: f.receiptRaw }); return; }
    if (url.pathname.startsWith('/docs/stop-research/') && f.bundle) { await route.fulfill({ contentType: 'application/json', body: f.bundle }); return; }
    await route.continue();
  });
  await page.addInitScript(({ now, dataUrl, theme }) => {
    window.SCStock = { now, dataUrl };
    localStorage.setItem('sc-theme', theme);
    localStorage.setItem('spicystock:lens:v1', JSON.stringify({ bursts: 'all', 'setting-up': 'all', sort: null }));
    window.__inspectionCopies = 0;
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { window.__inspectionCopies++; } } });
  }, { now: fixture.now, dataUrl: canonical || !fixture.reader ? '/decision-publication.json' : null, theme });
  await page.goto(base + '/docs/index.html#/explore/setting-up', { waitUntil: 'load' });
  await page.waitForFunction(() => document.documentElement.hasAttribute('data-ss-rendered') && SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
  return { page, context, requests, errors, state };
}
async function reveal(page) {
  await page.locator('#morning-open').click();
  await page.locator('[data-stop-research] > summary').click();
  await page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.stopResearch.status().state));
}
async function capture(page, name) {
  if (!shotsDir) return;
  await mkdir(shotsDir, { recursive: true });
  await page.screenshot({ path: path.join(shotsDir, name + '.png') });
}
async function actualCases(browser, base) {
  const fixture = await retained(), data = JSON.parse(fixture.canonical);
  for (const [width, theme, canonical] of [[1280, 'dark', false], [390, 'light', false], [390, 'dark', true]]) {
    const label = `retained ${width}/${theme}/${canonical ? 'canonical' : 'reader'}`;
    const tab = await launch(browser, base, fixture, { width, theme, canonical }), { page } = tab;
    try {
      await page.locator('#decision-gates > details > summary').click();
      check(label + ': anticipation family is visible', await page.locator('[data-anticipation-wait]').count() === 1);
      eq(label + ': all five original anticipation rows in original order', await page.locator('[data-anticipation-refusal]').evaluateAll(nodes => nodes.map(node => node.dataset.anticipationRefusal)), topRows(data).map(row => row.ticker));
      check(label + ': reaction family stays distinct', /reaction/i.test(await text(page, '[data-independent-gates]')));
      eq(label + ': anticipation count is five with zero admitted', await page.locator('[data-anticipation-wait]').evaluate(node => [node.dataset.topCount, node.dataset.ticketCount]), ['5', '0']);
      eq(label + ': quiet names are separately counted without becoming top plans', await page.locator('[data-anticipation-wait]').getAttribute('data-quiet-count'), String(data.watchlist.also_quiet.filter(row => !data.watchlist.top.some(top => top.ticker === row.ticker)).length));
      for (const row of topRows(data)) {
        const said = await text(page, `[data-anticipation-refusal="${row.ticker}"]`);
        check(label + ': ' + row.ticker + ' exact original refusal remains readable', said.toLowerCase().includes(row.plan.reason.toLowerCase()));
      }
      await page.locator('[data-anticipation-wait]').scrollIntoViewIfNeeded();
      await capture(page, 'decision-family-' + width + '-' + theme + (canonical ? '-canonical' : ''));
      const before = await authority(page), requestStart = tab.requests.length;
      await reveal(page);
      eq(label + ': exact retained comparison loaded', SCStockState(await page.evaluate(() => SCStock.stopResearch.status())), 'loaded');
      eq(label + ': each cohort row offers one recorded chart inspection', await page.locator(researchSelector).evaluateAll(nodes => nodes.map(node => node.dataset.stopInspect)), topRows(data).map(row => row.ticker));
      eq(label + ': research creates no order/prepare/copy controls', await page.locator('[data-stop-research] [data-copy], [data-stop-research] [data-order], [data-stop-research] [data-handoff-prepare]').count(), 0);
      const action = page.locator('[data-stop-inspect="KE"]');
      if (await action.count()) {
        await page.locator('[data-stop-row="KE"]').evaluate(node => node.scrollIntoView({ block: 'start' }));
        await capture(page, 'decision-research-' + width + '-' + theme + (canonical ? '-canonical' : ''));
        await action.focus();
        await capture(page, 'decision-inspect-control-' + width + '-' + theme + (canonical ? '-canonical' : ''));
        await page.keyboard.press('Enter');
        await page.waitForFunction(() => !document.getElementById('morning-desk').open && location.hash === '#/explore/setting-up/KE');
        eq(label + ': keyboard inspection routes to the original KE', await page.evaluate(() => [location.hash, document.getElementById('detail-h2').textContent, document.activeElement.id]), ['#/explore/setting-up/KE', 'KE', 'detail']);
        check(label + ': original chart and withheld baseline are readable', await page.locator('#detail .sc-chart svg').count() > 0 && (await text(page, '#detail')).toLowerCase().includes(data.watchlist.top.find(row => row.ticker === 'KE').plan.reason.toLowerCase()));
        await capture(page, 'decision-chart-' + width + '-' + theme + (canonical ? '-canonical' : ''));
        await page.goBack();
        await page.waitForFunction(() => location.hash !== '#/explore/setting-up/KE');
        check(label + ': inspection preserves browser Back', (await page.evaluate(() => location.hash)).startsWith('#/explore/setting-up'));
      }
      const after = await authority(page);
      eq(label + ': inspection cannot mutate source/model/private storage or observations', [after.data, after.model, after.storage, after.morning], [before.data, before.model, before.storage, before.morning]);
      eq(label + ': inspection cannot copy a ticket', await page.evaluate(() => window.__inspectionCopies), 0);
      check(label + ': only receipt and digest bundle are read on research open', tab.requests.slice(requestStart).every(request => /\/docs\/stop-research(?:\.json|\/[a-f0-9]{64}\.json)$/.test(new URL(request.url).pathname)));
      check(label + ': no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      eq(label + ': no uncaught browser errors', tab.errors, []);
    } finally { await tab.context.close(); }
  }
}
const SCStockState = status => status.state;

async function replacementCases(browser, base) {
  const fixture = await producer('priority'), tab = await launch(browser, base, fixture), { page } = tab;
  try {
    await reveal(page);
    const there = await page.locator('[data-stop-inspect="COIL"]').count();
    check('same-ticker replacement: genuine source has an inspection action', there === 1);
    if (!there) return;
    await page.evaluate(() => { window.__oldInspectionButton = document.querySelector('[data-stop-inspect="COIL"]'); window.__oldInspectionStatus = document.querySelector('[data-stop-inspect-status]'); });
    // Same measured session and ticker, independently generated publication.
    // No stored canonical is rewritten; the actual refresh consumes raw bytes.
    const next = await producer('red');
    tab.state.fixture = next;
    await page.locator('#check-updates').evaluate(node => node.click());
    await page.waitForFunction(expected => SCStock.observations.facts().recordHash === expected && !SCStock.observations.facts().pending, sha(next.reader));
    const before = await page.evaluate(() => ({ hash: location.hash, selected: document.getElementById('detail-h2').textContent, copies: window.__inspectionCopies }));
    await page.evaluate(() => window.__oldInspectionButton.click());
    eq('same-ticker replacement: detached old DOM action cannot navigate or copy', await page.evaluate(() => ({ hash: location.hash, selected: document.getElementById('detail-h2').textContent, copies: window.__inspectionCopies })), before);
    check('same-ticker replacement: old action explains original publication refusal', /changed|publication|match|unavailable/i.test(await page.evaluate(() => window.__oldInspectionStatus.textContent)));
    eq('same-ticker replacement: genuine replacement ticker still exists', await page.evaluate(() => !!SCStock.model.byId['setting-up:COIL']), true);
    eq('same-ticker replacement: raw reader binding is the actual replacement', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(next.reader));
    eq('same-ticker replacement: no uncaught browser errors', tab.errors, []);
  } finally { await tab.context.close(); }
}

async function missingCases(browser, base) {
  const fixture = await producer('current'), tab = await launch(browser, base, fixture), { page } = tab;
  try {
    // Labelled malformed/legacy display copies over the producer shell: absent
    // plan, absent reason and explicit zero are different recorded facts.
    const copy = JSON.parse(fixture.canonical);
    copy.fixture = 'synthetic missing decision evidence display control';
    copy.watchlist.top = copy.watchlist.top.slice(0, 3);
    copy.watchlist.top[0].plan = null;
    copy.watchlist.top[1].plan.reason = null;
    copy.watchlist.top[1].plan.shares = null;
    copy.watchlist.top[2].plan.shares = 0;
    copy.cash_budget.cut = []; copy.cash_budget.skipped = [];
    await page.evaluate(data => { SCStock.render(data, new Date('2026-10-10T09:20:00Z')); document.querySelector('#decision-gates > details').open = true; }, copy);
    const missing = await text(page, '[data-anticipation-refusal="MG"]'), unknown = await text(page, '[data-anticipation-refusal="KE"]'), zero = await text(page, '[data-anticipation-refusal="ZIM"]');
    check('missing plan: unavailable evidence remains explicit', /(?:plan|planning).*(?:unavailable|not recorded|no plan)|(?:unavailable|not recorded).*plan/i.test(missing));
    check('unknown reason: refusal reason remains unavailable', /reason.*unavailable|unavailable.*reason/i.test(unknown));
    check('zero shares: original refusal is not promoted to a ticket', !!zero && (await page.locator('[data-anticipation-wait]').getAttribute('data-ticket-count')) === '0');
    for (const [name, edit, expected] of [
      ['recorded planner exception', row => { row.evidence.planning.error = 'synthetic anticipation planner exception'; }, 'synthetic anticipation planner exception'],
      ['recorded plan-error gate', row => { row.evidence.planning.error = null; row.evidence.gate = { reason: 'plan_error', detail: 'synthetic recorded anticipation gate failure', ticket: false }; }, 'synthetic recorded anticipation gate failure'],
      ['recorded plan-error missing detail', row => { row.evidence.planning.error = null; row.evidence.gate = { reason: 'plan_error', detail: null, ticket: false }; }, 'planner error without further detail']
    ]) {
      const failed = structuredClone(copy); edit(failed.watchlist.top[0]);
      if (name === 'recorded plan-error gate') failed.breadth.regime = { ...failed.breadth.regime, verdict: 'red', size_multiplier: 0 };
      await page.evaluate(data => { SCStock.render(data, new Date('2026-10-10T09:20:00Z')); document.querySelector('#decision-gates > details').open = true; }, failed);
      const said = await text(page, '[data-anticipation-refusal="MG"]');
      check(name + ': recorded failure stays visible instead of unknown', said.includes(expected) && /Planning failed/i.test(said), said);
      check(name + ': publication market limitation remains independent', (await text(page, '[data-independent-gates]')).includes('market ' + failed.breadth.regime.verdict.toUpperCase()));
    }
    await page.evaluate(data => { const unknown = structuredClone(data); delete unknown.watchlist.top; SCStock.render(unknown, new Date('2026-10-10T09:20:00Z')); document.querySelector('#decision-gates > details').open = true; }, copy);
    eq('unknown shortlist: absent count cannot become zero', await page.locator('[data-anticipation-wait]').evaluate(node => [node.dataset.topCount, node.dataset.ticketCount]), ['unknown', 'unknown']);
    check('unknown shortlist: missing coverage explicit', /not recorded.*unknown/i.test(await text(page, '[data-anticipation-counts]')));
    const empty = await producer('empty');
    await page.evaluate(data => { SCStock.render(data, new Date('2026-10-10T09:20:00Z')); document.querySelector('#decision-gates > details').open = true; }, JSON.parse(empty.canonical));
    eq('genuine empty cohort: explicit zero shortlist', await page.locator('[data-anticipation-wait]').evaluate(node => [node.dataset.topCount, node.dataset.ticketCount]), ['0', '0']);
    eq('genuine empty cohort: no fabricated refusal rows', await page.locator('[data-anticipation-refusal]').count(), 0);
    const priority = await producer('priority');
    await page.evaluate(data => SCStock.render(data, new Date('2026-10-10T09:20:00Z')), JSON.parse(priority.canonical));
    eq('anticipation-only producer ticket: global zero-ticket waiting is hidden', await page.locator('#decision-gates').isHidden(), true);
    eq('missing/unknown/zero cases: no uncaught errors', tab.errors, []);
  } finally { await tab.context.close(); }
}

async function privateCases(browser, base) {
  const fixture = await cashFixture(), tab = await launch(browser, base, fixture), { page } = tab;
  try {
    await page.waitForFunction(() => SCStock.observations.facts().state === 'loaded');
    await page.locator('#morning-open').click();
    await page.locator('.ss-morning__prep > summary').click();
    await page.locator('#morning-cash').fill('2000');
    await page.locator('#morning-preview-fees').fill('1');
    await page.locator('#morning-preview-quantity').fill('2');
    await page.locator('[data-handoff-prepare]').click();
    await page.waitForFunction(() => SCStock.handoff.list().length === 1);
    await page.locator('[data-handoff-report] > summary').click();
    const field = page.locator('[data-handoff-field="submitted_quantity"]');
    await field.fill('3'); await field.focus();
    await page.evaluate(() => { window.__inspectionPrivateInput = document.querySelector('[data-handoff-field="submitted_quantity"]'); window.__inspectionCashInput = document.getElementById('morning-cash'); });
    const before = await authority(page), requestStart = tab.requests.length;
    const refs = identity(fixture, topRows(JSON.parse(fixture.canonical))[0], await page.evaluate(() => SCStock.observations.facts()));
    const available = await page.evaluate(() => typeof SCStock.inspectRecordedChart === 'function');
    check('private continuity: shared exact-evidence inspection API exists', available);
    if (!available) return;
    const result = await page.evaluate(refs => SCStock.inspectRecordedChart(refs), refs);
    check('private continuity: exact producer plan inspects successfully', result.ok, result.reason);
    await page.locator('#morning-open').click();
    eq('private continuity: dirty report node/value survive inspection route and reopen', await page.evaluate(() => [window.__inspectionPrivateInput === document.querySelector('[data-handoff-field="submitted_quantity"]'), window.__inspectionPrivateInput.value]), [true, '3']);
    eq('private continuity: cash node and exact local value survive', await page.evaluate(() => [window.__inspectionCashInput === document.getElementById('morning-cash'), window.__inspectionCashInput.value]), [true, '2000']);
    const after = await authority(page);
    eq('private continuity: unsaved report was neither written nor discarded', [after.storage, after.data, after.model], [before.storage, before.data, before.model]);
    eq('private continuity: source inspection makes zero requests', tab.requests.slice(requestStart), []);
    eq('private continuity: no copies or additional drafts', await page.evaluate(() => [window.__inspectionCopies, SCStock.handoff.list().length]), [0, 1]);
    for (const [name, edit] of [
      ['wrong actual publication bytes', refs => { refs.recordHash = '0'.repeat(64); }],
      ['wrong canonical binding', refs => { refs.publication.data_sha256 = '0'.repeat(64); }],
      ['wrong original evidence ID', refs => { refs.evidence.id = '0'.repeat(64); }],
      ['wrong source bars digest', refs => { refs.evidence.source_sha256 = '0'.repeat(64); }],
      ['wrong original plan digest', refs => { refs.evidence.plan_sha256 = '0'.repeat(64); }],
      ['missing identity', refs => { delete refs.evidence; }],
      ['unknown family', refs => { refs.kind = 'future'; }],
      ['missing ticker', refs => { refs.ticker = 'ZZMISSING'; }]
    ]) {
      const bad = structuredClone(refs); edit(bad);
      await field.focus();
      const snapshot = await page.evaluate(() => [location.hash, document.activeElement === window.__inspectionPrivateInput]);
      const result = await page.evaluate(refs => SCStock.inspectRecordedChart(refs), bad);
      check(name + ': inspection is refused with reason', result.ok === false && !!result.reason);
      eq(name + ': refusal preserves route and dirty focus', await page.evaluate(() => [location.hash, document.activeElement === window.__inspectionPrivateInput]), snapshot);
    }
    eq('private continuity: no uncaught browser errors', tab.errors, []);
  } finally { await tab.context.close(); }
}

export async function checkDecisionInspection({ browser, base, check: sharedCheck, shotsDir: sharedShots }) {
  const localCheck = check, localShots = shotsDir;
  if (sharedCheck) check = sharedCheck;
  if (sharedShots) shotsDir = sharedShots;
  try {
    for (const [name, suite] of [['actual', actualCases], ['replacement', replacementCases], ['unknown', missingCases], ['private', privateCases]]) {
      try { await suite(browser, base); } catch (error) { check('decision inspection ' + name + ': suite completes', false, error.stack); }
    }
  } finally { check = localCheck; shotsDir = localShots; }
}

async function main() {
  const { host, base } = await server();
  let browser;
  try {
    const { chromium } = await playwright();
    browser = await chromium.launch({ headless: true });
    for (const [name, suite] of [['actual', actualCases], ['replacement', replacementCases], ['unknown', missingCases], ['private', privateCases]]) {
      if (!run(name)) continue;
      const begin = results.length;
      try { await suite(browser, base); } catch (error) { check(name + ': suite completes', false, error.stack); }
      cases.push({ name, checks: results.length - begin });
    }
  } catch (error) { check('browser test launch completes', false, error.stack); }
  finally { if (browser) await browser.close(); await new Promise(resolve => host.close(resolve)); }
  const failures = results.filter(result => !result.pass);
  const output = { schema_version: 1, status: failures.length ? 'FAIL' : 'PASS', scope: 'Local retained publication and producer browser controls; labelled synthetic private input and malformed display cases; no live providers, broker, real user profile or shared source mutations.',
    runtime: process.version, source_sha256: Object.fromEntries(await Promise.all([
      ['docs/app.js', process.env.SCSTOCK_APP], ['docs/app-morning.js', process.env.SCSTOCK_MORNING], ['docs/app-stop-research.js', process.env.SCSTOCK_STOP_RESEARCH]
    ].map(async ([name, override]) => [name, sha(await readFile(override || path.join(ROOT, name)))]))),
    cases, checks_passed: results.length - failures.length, checks_total: results.length, results };
  if (reportPath) { await mkdir(path.dirname(path.resolve(reportPath)), { recursive: true }); await writeFile(reportPath, JSON.stringify(output, null, 2) + '\n'); }
  console.log(`Decision inspection: ${output.checks_passed}/${output.checks_total} checks pass`);
  process.exitCode = failures.length ? 1 : 0;
}
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename)) await main();
