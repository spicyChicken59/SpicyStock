/* Dated research observations: the real collector's receipts over the stop-research
   fixtures, bound in the browser to the exact publication and cohort. Malformed
   cases alter served transport copies, never the stored fixtures. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const STOP = path.join(ROOT, 'tests/fixtures/stop-research'), DIR = path.join(ROOT, 'tests/fixtures/research-observations');
const PRIVATE = 'ZZPRIVATE-research-observation-345.67';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const observationRequests = requests => requests.filter(request => /\/research-observations\.json$/.test(new URL(request.url).pathname));
const researchRequests = requests => requests.filter(request => /\/(?:stop-research(?:\.json|\/)|research-observations\.json)/.test(new URL(request.url).pathname));
const actions = '[data-copy], [data-order], [data-handoff-prepare], [data-follow], [data-save]';
const money = x => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 }).format(x);

async function file(dir, name) {
  const raw = await readFile(path.join(dir, name));
  return name.endsWith('.gz') ? gunzipSync(raw) : raw;
}
async function cohort(name) {
  const [publication, reader, receiptRaw, raw] = await Promise.all([
    file(STOP, name + '-publication.json.gz'), file(STOP, name + '-reader.json.gz'), file(STOP, name + '-receipt.json'), file(STOP, name + '-bundle.json')]);
  return { publication, reader, receiptRaw, receipt: JSON.parse(receiptRaw), raw, bundle: JSON.parse(raw) };
}
async function observation(name) {
  const raw = await file(DIR, name + '.json');
  return { name, raw, value: JSON.parse(raw) };
}

export async function checkResearchObservations({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- dated research observations: exact publication and cohort, one single-venue snapshot, no ready label or size');
  const state = page => page.evaluate(() => SCStock.researchObservations.status());
  const stopState = page => page.evaluate(() => SCStock.stopResearch.status());
  const settled = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.stopResearch.status().state) && SCStock.researchObservations.status().settled);
  const reveal = async page => { await page.locator('[data-stop-research] > summary').click(); await settled(page); };
  const summary = page => page.locator('[data-research-observations-summary]').textContent();
  const host = (page, ticker) => page.locator('[data-research-observation-host="' + ticker + '"]');
  const section = (page, ticker) => page.locator('[data-research-observation="' + ticker + '"]');
  const value = (page, ticker, key) => section(page, ticker).locator('[data-observation-value="' + key + '"]').textContent();
  const snapshot = page => page.evaluate(async () => {
    const digest = async value => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(value)))), byte => byte.toString(16).padStart(2, '0')).join('');
    const [data, model, storage] = await Promise.all([digest(SCStock.data), digest(SCStock.model), digest(localStorage)]);
    return { data, model, storage, morning: SCStock.observations.facts(),
      controls: [...document.querySelectorAll('[data-copy], [data-order], [data-handoff-prepare]')].map(node => ({
        copy: node.getAttribute('data-copy'), order: node.getAttribute('data-order'), prepare: node.hasAttribute('data-handoff-prepare'), disabled: node.disabled })) };
  });
  // The page clock sits a minute after the served observation was generated (or
  // after the cohort's when none is served): an observation from the page's
  // future is refused, which the boundary cases exercise on purpose.
  const clockFor = (source, served) => new Date(Date.parse(served && served.value ? served.value.generated_at : source.receipt.timing.generated_at) + 60000).toISOString();
  async function setup(source, served, options = {}) {
    const requests = [], transport = { current: served };
    const tab = await open(browser, base, options.canonical ? '/observation-canonical-control.json' : null, options.now || clockFor(source, served), options.width || 1280, {
      theme: options.theme || 'dark', reducedMotion: 'reduce', lens: 'all', hash: options.hash || '#/explore/setting-up/KE',
      beforeLoad: async (page, context) => {
        await context.addCookies([{ name: 'observation_private_cookie', value: PRIVATE, url: base }]);
        page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData(), headers: request.headers() }));
        await page.addInitScript(privateValue => {
          localStorage.setItem('research-observation-private-sentinel', privateValue);
          window.__observationFetches = [];
          const fetch = window.fetch;
          window.fetch = function(url, options = {}) {
            if (/\/research-observations\.json/.test(String(url))) window.__observationFetches.push({ url: String(url), credentials: options.credentials, mode: options.mode, redirect: options.redirect, referrerPolicy: options.referrerPolicy, body: options.body || null, method: options.method || 'GET' });
            return fetch.apply(this, arguments);
          };
        }, PRIVATE);
        await page.route('**/docs/reader.json', route => route.fulfill({ contentType: 'application/json', body: source.reader }));
        await page.route('**/observation-canonical-control.json', route => route.fulfill({ contentType: 'application/json', body: source.publication }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: '{}' }));
        await page.route('**/stop-research.json', route => route.fulfill({ contentType: 'application/json', body: source.receiptRaw }));
        await page.route('**/stop-research/*.json', route => route.fulfill({ contentType: 'application/json', body: source.raw }));
        await page.route('**/research-observations.json', async route => {
          const current = transport.current;
          if (current === null) { await route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' }); return; }
          await route.fulfill({ status: current.status || 200, contentType: 'application/json', body: Buffer.isBuffer(current.raw) ? current.raw : Buffer.from(typeof current.raw === 'string' ? current.raw : JSON.stringify(current.value)) });
        });
        if (options.beforeLoad) await options.beforeLoad(page, context);
      }
    });
    await tab.page.waitForFunction(() => SCStock.researchObservations && SCStock.stopResearch && !!SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    await tab.page.locator('#morning-open').click();
    return { ...tab, requests, transport };
  }
  const fit = async (page, label) => check(label + ': observation fits the dialog and page', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
  const noActions = async (page, label) => eq(label + ': the observation exposes no order, copy, prepare, follow or save action', await page.locator('[data-stop-research]').locator(actions).count(), 0);
  const noReadyLabel = async (page, label) => {
    const texts = await page.locator('[data-research-observation], [data-research-observations-summary]').allTextContents();
    const text = texts.join(' ').replace(/not a ready signal/g, '').replace(/None is a ready signal/g, '');
    check(label + ': nothing the observation prints is labelled ready, a buy, a fill or a quantity to place', texts.length > 0 && !/\bready\b/i.test(text) && !/\bbuy\b/i.test(text) && !/\bfill(?:ed|s)?\b/i.test(text) && !/\bshares?\b/i.test(text));
  };
  const capture = async (page, name, ticker) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true });
    await page.locator('[data-research-observations-summary]').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(shotsDir, name + '.png') });
    if (ticker && await section(page, ticker).count()) {
      await section(page, ticker).evaluate(node => node.scrollIntoView({ block: 'start' }));
      await page.screenshot({ path: path.join(shotsDir, name + '-' + ticker + '.png') });
    }
  };

  const current = await cohort('current'), observed = await observation('observed');
  const rows = Object.fromEntries(observed.value.rows.map(row => [row.ticker, row]));
  const timeWords = stamp => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date(stamp));
  const normal = text => text.replace(/\s/g, ' ');

  for (const [width, theme, canonical] of [[1280, 'dark', false], [390, 'light', false], [390, 'dark', true]]) {
    const label = width + '/' + theme + (canonical ? '/canonical' : ''), tab = await setup(current, observed, { width, theme, canonical });
    const { page, context, requests, errors } = tab;
    try {
      eq(label + ': a closed research panel performs zero observation requests', observationRequests(requests).length, 0);
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('345.67'); await page.locator('#morning-cash').focus();
      const before = await snapshot(page), requestsBefore = requests.length;
      await page.evaluate(() => { window.__observationCashNode = document.getElementById('morning-cash'); document.querySelector('[data-stop-research]').open = true; });
      await settled(page);
      eq(label + ': the cohort loads', (await stopState(page)).state, 'loaded');
      eq(label + ': the real collector receipt binds to the exact publication and cohort', [(await state(page)).state, (await state(page)).status, (await state(page)).rows], ['loaded', 'observed', 2]);
      eq(label + ': only the two allocation-fit rows carry an observation host', await page.locator('[data-research-observation-host]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-research-observation-host'))), ['KE', 'PSNL']);
      eq(label + ': refused rows get no observation', await page.locator('[data-stop-row="MG"] [data-research-observation], [data-stop-row="ZIM"] [data-research-observation], [data-stop-row="SN"] [data-research-observation]').count(), 0);
      const words = normal(await summary(page));
      check(label + ': the summary dates the snapshot, counts rows and one request, and names what was not checked', /^Dated observation · /.test(words) && words.includes(normal(timeWords(observed.value.generated_at))) && /2 research rows · one IEX snapshot request/.test(words) && /halts, volume pace, issuer news and earnings were not checked/.test(words));
      for (const ticker of ['KE', 'PSNL']) {
        const row = rows[ticker], quote = row.quote, trade = row.trade;
        eq(label + ': ' + ticker + ' prints the recorded bid, ask and sizes', await value(page, ticker, 'bid-ask'), money(quote.bid) + ' × ' + quote.bid_size + ' / ' + money(quote.ask) + ' × ' + quote.ask_size);
        eq(label + ': ' + ticker + ' prints the recorded spread', await value(page, ticker, 'spread'), money(quote.spread_usd) + ' (' + quote.spread_pct.toFixed(2) + '%)');
        check(label + ': ' + ticker + ' prints the recorded print as a print, not a quote', normal(await value(page, ticker, 'trade')).startsWith(money(trade.price) + ' at ' + normal(timeWords(trade.timestamp))) && /a print, not a current quote/.test(await value(page, ticker, 'trade')));
        eq(label + ': ' + ticker + ' prints the published levels', await value(page, ticker, 'levels'), 'trigger ' + money(row.levels.trigger) + ' · limit ' + money(row.levels.limit) + ' · stop ' + money(row.levels.stop));
        check(label + ': ' + ticker + ' names the unchecked coverage beside the observation', /trading halts, delayed volume pace, issuer news and earnings/.test(await section(page, ticker).textContent()) && /not news clearance/.test(await section(page, ticker).textContent()));
      }
      eq(label + ': KE ask is placed below the published trigger', await value(page, 'KE', 'ask-state'), 'below the published trigger');
      eq(label + ': PSNL ask is placed inside the band and said to be a position, not a signal', await value(page, 'PSNL', 'ask-state'), 'between the published trigger and limit (a position, not a signal)');
      eq(label + ': the research rows keep their hypothetical sizing untouched', await Promise.all(['KE', 'PSNL'].map(ticker => page.locator('[data-stop-row="' + ticker + '"] [data-stop-value="research-shares"]').textContent())), ['1', '3']);
      await noActions(page, label); await noReadyLabel(page, label);
      eq(label + ': private cash node, value and focus survive the observation', await page.evaluate(() => [document.getElementById('morning-cash') === window.__observationCashNode, window.__observationCashNode.value, document.activeElement === window.__observationCashNode]), [true, '345.67', true]);
      eq(label + ': the observation cannot mutate publication, model, storage, orders or morning authority', await snapshot(page), before);
      eq(label + ': opening research reads the receipt, its bundle and the observation and nothing else', requests.slice(requestsBefore).map(request => new URL(request.url).pathname), ['/docs/stop-research.json', '/docs/' + current.receipt.bundle.path, '/docs/research-observations.json']);
      check(label + ': the observation transport carries no cookie, referrer, body, private value or query', observationRequests(requests).every(request => request.method === 'GET' && !request.body && !request.headers.cookie && !request.headers.referer && !request.url.includes(PRIVATE) && !request.url.includes('345.67') && !new URL(request.url).search));
      check(label + ': the observation fetch omits credentials and referrer and refuses redirects', (await page.evaluate(() => window.__observationFetches)).every(request => request.credentials === 'omit' && request.referrerPolicy === 'no-referrer' && request.mode === 'same-origin' && request.redirect === 'error' && request.body === null));
      await fit(page, label); await capture(page, 'research-observation-' + width + '-' + theme + (canonical ? '-canonical' : ''), 'KE');
      eq(label + ': a valid observation causes no browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  const variants = Object.fromEntries(await Promise.all(['partial', 'outage', 'no-credentials', 'before-window', 'expired', 'wrong-session', 'missing-cohort', 'stale-cohort', 'followup'].map(async name => [name, await observation(name)])));
  const states = await setup(current, variants.partial);
  try {
    const { page, transport } = states;
    await reveal(page);
    eq('partial: a stale print and a crossed quote load as partial', [(await state(page)).state, (await state(page)).status], ['loaded', 'partial']);
    check('partial: KE crossed quote is named invalid and not shown', /invalid provider quote/.test(await value(page, 'KE', 'bid-ask')));
    eq('partial: KE ask has no position against the levels', await value(page, 'KE', 'ask-state'), 'unknown — no recent observation');
    check('partial: PSNL stale print is marked stale', /\(stale\)/.test(await value(page, 'PSNL', 'trade')));
    eq('partial: PSNL stale print has no position', await value(page, 'PSNL', 'trade-state'), 'unknown — no recent observation');
    check('partial: the summary says some prices were stale, invalid or missing', /stale, invalid or missing/.test(await summary(page)));
    await capture(page, 'research-observation-partial-1280-dark', 'KE');
    const reloadTo = async served => {
      transport.current = served;
      await page.evaluate(now => { SCStock.now = now; SCStock.reclock(); return SCStock.researchObservations.reload(); }, clockFor(current, served));
      await settled(page);
    };
    await reloadTo(variants.outage);
    eq('outage: one failed request is provider unavailable', [(await state(page)).status, variants.outage.value.source.requests], ['provider_unavailable', 1]);
    check('outage: the summary counts its single failed request', /one IEX snapshot request/.test(await summary(page)));
    check('outage: the row says the provider returned an error, with no price', /unavailable — the provider returned an error/.test(await value(page, 'KE', 'bid-ask')) && /No price was observed/.test(await summary(page)));
    await reloadTo(variants['no-credentials']);
    eq('no credentials: zero requests, provider unavailable', [(await state(page)).status, variants['no-credentials'].value.source.requests], ['provider_unavailable', 0]);
    check('no credentials: the summary reports zero requests, never one', /zero IEX snapshot requests/.test(await summary(page)) && !/one IEX snapshot request/.test(await summary(page)));
    await capture(page, 'research-observation-no-credentials-1280-dark', 'KE');
    check('no credentials: the row names the missing credentials', /no provider credentials were configured/.test(await value(page, 'PSNL', 'bid-ask')));
    for (const [name, reasonWords] of [['before-window', 'before the half-hour collection window'], ['expired', 'after the entry window ended'], ['wrong-session', 'a day other than the applicable session']]) {
      await reloadTo(variants[name]);
      eq(name + ': an inapplicable receipt loads with its reason and no row', [(await state(page)).status, (await state(page)).rows, await page.locator('[data-research-observation]').count()], ['inapplicable', 0, 0]);
      check(name + ': the summary names the reason and zero provider requests', (await summary(page)).includes(reasonWords) && /Zero provider requests were made/.test(await summary(page)));
      eq(name + ': every host explains the absence rather than an empty box', await page.locator('[data-research-observation-note]').count(), 2);
    }
    for (const name of ['missing-cohort', 'stale-cohort']) {
      await reloadTo(variants[name]);
      eq(name + ': a receipt collected over another or no cohort cannot describe this one', (await state(page)).state, 'unavailable');
      check(name + ': the refusal names the cohort', /another research cohort/.test((await state(page)).issue));
      eq(name + ': no observation section appears', await page.locator('[data-research-observation]').count(), 0);
    }
    await reloadTo(variants.followup);
    eq('followup: a later observation bound to its predecessor loads', [(await state(page)).state, (await state(page)).status], ['loaded', 'observed']);
    await reloadTo(null);
    eq('404: an absent optional file is unavailable, not an error', (await state(page)).state, 'unavailable');
    check('404: the summary says none has been published', /No dated observation has been published for this cohort/.test(await summary(page)));
    eq('404: the cohort rows remain readable', await page.locator('[data-stop-row]').count(), 5);
    await reloadTo({ status: 500, raw: 'server error' });
    eq('500: a failed read is unavailable', (await state(page)).state, 'unavailable');
    await reloadTo({ raw: Buffer.alloc(64 * 1024 + 1, 0x20) });
    check('oversized: the byte cap refuses before parsing', /size limit/.test((await state(page)).issue));
    await reloadTo({ raw: Buffer.concat([Buffer.from([239, 187, 191]), observed.raw]) });
    eq('BOM: a byte-order mark is not accepted JSON', (await state(page)).state, 'unavailable');
    await reloadTo(observed);
    eq('retry recovers the genuine observation', [(await state(page)).state, (await state(page)).status], ['loaded', 'observed']);
    await page.evaluate(expires => { SCStock.now = new Date(Date.parse(expires) + 1000).toISOString(); SCStock.researchObservations.update(SCStock.data); }, observed.value.expires_at);
    check('expiry: past expires_at the summary and sections read as expired', /^Expired dated observation/.test(await summary(page)) && /^Expired dated IEX observation/.test(await section(page, 'KE').locator('h5').textContent()));
    eq('expiry: sections stay readable with their recorded values', await value(page, 'KE', 'bid-ask'), money(rows.KE.quote.bid) + ' × ' + rows.KE.quote.bid_size + ' / ' + money(rows.KE.quote.ask) + ' × ' + rows.KE.quote.ask_size);
    await noActions(page, 'expiry');
    await page.evaluate(() => SCStock.researchObservations.update(null));
    eq('a withdrawn publication clears every observation section', await page.locator('[data-research-observation]').count(), 0);
    eq('handled transports produce no page exceptions', [...states.errors], []);
  } finally { await states.context.close(); }

  const precision = await setup(current, observed, { width: 390, theme: 'light' });
  try {
    const { page, transport } = precision;
    await reveal(page);
    const original = await snapshot(page);
    for (const suffix of ['', '-offset']) {
      for (const [name, expected] of [['age-60s', 'recent'], ['age-60s-plus-microsecond', 'stale'], ['future-5s', 'recent'], ['future-5s-plus-microsecond', 'invalid']]) {
        const label = name + suffix, served = await observation(label);
        transport.current = served;
        await page.evaluate(now => { SCStock.now = now; return SCStock.researchObservations.reload(); }, clockFor(current, served));
        await settled(page);
        eq(label + ': producer-derived quote and trade bind without timestamp truncation', [(await state(page)).state, (await state(page)).status], ['loaded', expected === 'recent' ? 'observed' : 'partial']);
        eq(label + ': both producer states describe the exact collection boundary', [served.value.rows[0].quote.status, served.value.rows[0].trade.status], [expected, expected]);
        eq(label + ': the ask position is unknown unless the collected quote was recent', await value(page, 'KE', 'ask-state'), expected === 'recent' ? 'below the published trigger' : 'unknown — no recent observation');
        eq(label + ': the trade position is unknown unless the collected print was recent', await value(page, 'KE', 'trade-state'), expected === 'recent' ? 'below the published trigger' : 'unknown — no recent observation');
        check(label + ': the row identifies positions as at collection time', /Recent\/stale labels and level positions describe collection time/.test(await section(page, 'KE').textContent()));
        if (expected === 'stale') check(label + ': the accepted older prices remain visibly stale', /\(stale\)/.test(await value(page, 'KE', 'bid-ask')) && /\(stale\)/.test(await value(page, 'KE', 'trade')));
        if (expected === 'invalid') check(label + ': invalid future prices are not displayed', /invalid provider quote/.test(await value(page, 'KE', 'bid-ask')) && /invalid provider print/.test(await value(page, 'KE', 'trade')));
        eq(label + ': no publication, private state or authority changes', await snapshot(page), original);
        await noActions(page, label);
        if (label === 'age-60s-plus-microsecond-offset') await capture(page, 'research-observation-microsecond-stale-390-light', 'KE');
      }
    }
    for (const [name, expected] of [['locked-zero-spread', 'observed'], ['rounded-spread-tie', 'observed'], ['large-dollar-spread', 'observed'], ['midpoint-underflow', 'partial']]) {
      transport.current = await observation(name); await page.evaluate(() => SCStock.researchObservations.reload()); await settled(page);
      eq(name + ': producer-derived result loads', [(await state(page)).state, (await state(page)).status], ['loaded', expected]);
      if (expected === 'observed') eq(name + ': a legitimate spread stays readable', await value(page, 'KE', 'spread'), name === 'locked-zero-spread' ? '$0.00 (0.00%)' : name === 'rounded-spread-tie' ? '$0.027 (0.03%)' : '$999,999,999,999,900.00 (200.00%)');
      else {
        check(name + ': the invalid subnormal quote is not shown', /invalid provider quote/.test(await value(page, 'KE', 'bid-ask')));
        eq(name + ': a collapsed midpoint is never promoted against levels', await value(page, 'KE', 'ask-state'), 'unknown — no recent observation');
      }
      eq(name + ': no publication, private state or authority changes', await snapshot(page), original);
      await noActions(page, name);
    }
    eq('precise clocks and spreads produce no page exceptions', [...precision.errors], []);
  } finally { await precision.context.close(); }

  const boundary = await setup(current, observed);
  try {
    const { page, transport } = boundary;
    await reveal(page);
    eq('boundary control first loads the genuine observation', (await state(page)).status, 'observed');
    const original = await snapshot(page);
    const changed = edit => { const value = structuredClone(observed.value); edit(value); return { value }; };
    const cases = [
      ['canonical publication bytes', changed(v => { v.publication.data_sha256 = '0'.repeat(64); })],
      ['reader projection bytes', changed(v => { v.publication.reader_sha256 = '0'.repeat(64); })],
      ['cohort receipt bytes', changed(v => { v.cohort.receipt_sha256 = '0'.repeat(64); })],
      ['cohort bundle identity', changed(v => { v.cohort.bundle_sha256 = '0'.repeat(64); })],
      ['cohort binding flag', changed(v => { v.cohort.bound = false; })],
      ['duplicated row', changed(v => { v.rows.push(structuredClone(v.rows[0])); })],
      ['dropped row', changed(v => { v.rows.pop(); })],
      ['substituted ticker', changed(v => { v.rows[0].ticker = 'MG'; })],
      ['moved limit', changed(v => { v.rows[0].levels.limit += 0.01; })],
      ['moved entry floor', changed(v => { v.rows[0].levels.entry_low = 29.0; })],
      ['foreign evidence', changed(v => { v.rows[0].evidence.id = '0'.repeat(64); })],
      ['foreign projection', changed(v => { v.rows[0].projection_sha256 = '0'.repeat(64); })],
      ['forged band position', changed(v => { v.rows[0].price_checks.ask = 'within_published_band'; })],
      ['invented ready state', changed(v => { v.rows[0].price_checks.ask = 'ready'; })],
      ['stale print called recent', changed(v => { v.rows[0].trade.timestamp = new Date(Date.parse(v.generated_at) - 120000).toISOString(); })],
      ['missing quote with values', changed(v => { v.rows[0].quote.status = 'missing'; })],
      ['forged spread percentage', changed(v => { v.rows[0].quote.spread_pct = 9876.54; })],
      ['negative spread percentage', changed(v => { v.rows[0].quote.spread_pct = -0.1; })],
      ['wrong rounded spread percentage', changed(v => { v.rows[0].quote.spread_pct += 0.00000001; })],
      ['wrong rounded dollar spread', changed(v => { v.rows[0].quote.spread_usd += 0.00000001; })],
      ['quote without exchange called recent', changed(v => { v.rows[0].quote.bid_exchange = null; })],
      ['trade without exchange called recent', changed(v => { v.rows[0].trade.exchange = null; })],
      ['quote without conditions called recent', changed(v => { v.rows[0].quote.conditions = null; })],
      ['trade without conditions called recent', changed(v => { v.rows[0].trade.conditions = null; })],
      ['midpoint underflow called recent', changed(v => { Object.assign(v.rows[0].quote, { bid: 5e-324, ask: 5e-324, spread_usd: 0, spread_pct: 0 }); v.rows[0].price_checks.ask = 'below_stop'; })],
      ['sub-microsecond timestamp', changed(v => { v.rows[0].quote.timestamp = '2026-10-12T13:19:59.1234567+00:00'; })],
      ['invalid timestamp offset', changed(v => { v.rows[0].quote.timestamp = '2026-10-12T13:19:59+24:00'; })],
      ['expiry advanced one microsecond', changed(v => { v.expires_at = '2026-10-12T13:25:00.000001+00:00'; })],
      ['provider check before start by one microsecond', changed(v => { v.source.checked_at = '2026-10-12T13:19:59.999999+00:00'; })],
      ['crossed quote called recent', changed(v => { v.rows[0].quote.ask = v.rows[0].quote.bid - 0.01; })],
      ['failed source with prices', changed(v => { v.source.status = 'unavailable'; v.source.entitlement = 'unavailable'; v.source.error_kind = 'provider_error'; })],
      ['second request', changed(v => { v.source.requests = 2; })],
      ['observed prices with no request counted', changed(v => { v.source.requests = 0; })],
      ['consolidated feed claim', changed(v => { v.source.scope = 'consolidated'; })],
      ['forged status', changed(v => { v.status = 'partial'; })],
      ['forged reason', changed(v => { v.reason = 'wrong_session'; })],
      // Prints dated 2099 on applicable session 2026-10-12 are stale by session,
      // whatever the clock: the freshness replay is the rule this one exercises.
      ['future prints called recent', changed(v => { v.collection_started_at = '2099-10-12T13:20:00+00:00'; v.generated_at = '2099-10-12T13:20:01+00:00'; v.expires_at = '2099-10-12T13:25:01+00:00'; v.source.checked_at = '2099-10-12T13:20:00.500000+00:00'; v.rows.forEach(row => { row.quote.timestamp = '2099-10-12T13:20:00+00:00'; row.trade.timestamp = '2099-10-12T13:19:59+00:00'; }); })],
      // An inapplicable receipt has no row and no request, so nothing but the
      // page's own clock can refuse one that is simply from the future.
      ['future collection', (() => { const value = structuredClone(variants['before-window'].value); value.collection_started_at = '2099-10-12T12:30:00+00:00'; value.generated_at = '2099-10-12T12:30:00+00:00'; value.expires_at = '2099-10-12T12:35:00+00:00'; return { value }; })()],
      ['rehearsal over a real record', changed(v => { v.dry_run = true; })],
      ['wider request budget', changed(v => { v.policy.max_requests_per_run = 2; })],
      ['halts claimed checked', changed(v => { v.coverage.halts = 'checked'; })],
      ['dropped limits', changed(v => { v.limits = []; })],
      ['research sizing smuggled in', changed(v => { v.rows[0].research_shares = 1; })],
    ];
    for (const suffix of ['', '-offset']) {
      const oldPrint = structuredClone((await observation('age-60s-plus-microsecond' + suffix)).value);
      oldPrint.rows[0].quote.status = 'recent'; oldPrint.rows[0].trade.status = 'recent';
      oldPrint.rows[0].price_checks = { ask: 'below_entry_floor', trade: 'below_entry_floor' }; oldPrint.status = 'observed';
      cases.push(['60.000001 seconds called recent' + suffix, { value: oldPrint }]);
      const futurePrint = structuredClone((await observation('future-5s-plus-microsecond' + suffix)).value);
      futurePrint.rows[0].quote.status = 'recent'; futurePrint.rows[0].trade.status = 'recent';
      futurePrint.rows[0].price_checks = { ask: 'below_entry_floor', trade: 'below_entry_floor' }; futurePrint.status = 'observed';
      cases.push(['5.000001 future seconds called recent' + suffix, { value: futurePrint }]);
    }
    const largeSpread = structuredClone((await observation('large-dollar-spread')).value);
    largeSpread.rows[0].quote.spread_usd -= 0.125;
    cases.push(['adjacent float forged dollar spread', { value: largeSpread }]);
    for (const [name, served] of cases) {
      transport.current = served; await page.evaluate(() => SCStock.researchObservations.reload()); await settled(page);
      eq(name + ': a malformed observation is refused', (await state(page)).state, 'unavailable');
      eq(name + ': no observation section survives', await page.locator('[data-research-observation]').count(), 0);
      eq(name + ': the cohort, publication and private state are untouched', await snapshot(page), original);
    }
    eq('boundary cases produce no page exceptions', [...boundary.errors], []);
  } finally { await boundary.context.close(); }

  const canonicalBoundary = await setup(current, observed, { canonical: true });
  try {
    const { page, transport } = canonicalBoundary;
    await reveal(page);
    eq('canonical control first loads the genuine observation', (await state(page)).status, 'observed');
    const value = structuredClone(observed.value); value.publication.reader_sha256 = '0'.repeat(64);
    transport.current = { value }; await page.evaluate(() => SCStock.researchObservations.reload()); await settled(page);
    eq('canonical load: a reader digest the cohort does not carry is refused', (await state(page)).state, 'unavailable');
    eq('canonical load: no observation section survives the refusal', await page.locator('[data-research-observation]').count(), 0);
    eq('canonical boundary produces no page exceptions', [...canonicalBoundary.errors], []);
  } finally { await canonicalBoundary.context.close(); }

  const red = await cohort('red'), noRows = await observation('no-rows');
  const redTab = await setup(red, noRows, { hash: '#/explore', width: 390, theme: 'light' });
  try {
    await reveal(redTab.page);
    eq('red cohort: a fit-free cohort loads with no observed row', [(await state(redTab.page)).state, (await state(redTab.page)).status, (await state(redTab.page)).rows], ['loaded', 'no_research_rows', 0]);
    check('red cohort: the summary says no allocation fit existed and zero requests were made', /no allocation-fit research row/.test(await summary(redTab.page)) && /Zero provider requests/.test(await summary(redTab.page)));
    eq('red cohort: no host or section exists', await redTab.page.locator('[data-research-observation-host], [data-research-observation]').count(), 0);
    await fit(redTab.page, 'red cohort'); await capture(redTab.page, 'research-observation-red-390-light');
    eq('red cohort: no browser errors', [...redTab.errors], []);
  } finally { await redTab.context.close(); }

  const race = await setup(current, observed);
  try {
    await reveal(race.page);
    eq('replacement control starts loaded', (await state(race.page)).state, 'loaded');
    await race.page.evaluate(async raw => {
      const next = JSON.parse(raw); SCStock.render(next, new Date(SCStock.now)); await SCStock.observations.bind(next, raw);
    }, red.publication.toString('utf8'));
    await settled(race.page);
    eq('a replacement publication withdraws the old cohort and its observation', [(await stopState(race.page)).state, await race.page.locator('[data-research-observation]').count()], ['unavailable', 0]);
    eq('replacement produces no page exceptions', [...race.errors], []);
  } finally { await race.context.close(); }
}
