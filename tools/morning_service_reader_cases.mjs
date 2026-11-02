/* Explicit synthetic transport rehearsal. No service is deployed and no
   fixture becomes a current recommendation or a provider observation. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { withEndpoint } from './offline_shell.mjs';
const ROOT = path.resolve(import.meta.dirname, '..');
const ENDPOINT = 'https://receipts.example.invalid/morning.json';
const NOW = '2026-09-11T13:35:00Z';

export async function checkMorningServiceReader({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- optional morning receipt service: fixed private-free reads and bounded polling');
  const html = await readFile(path.join(ROOT, 'docs/index.html'), 'utf8');
  const raw = await readFile(path.join(ROOT, 'tests/fixtures/morning/full-publication.json'), 'utf8');
  const redRaw = await readFile(path.join(ROOT, 'tests/fixtures/morning/red-publication.json'), 'utf8');
  const observed = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/observed.json')));
  const halted = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/halted.json')));
  const resumed = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/resumed.json')));
  const outage = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/outage.json')));
  const facts = page => page.evaluate(() => SCStock.observations.facts());
  const wait = page => page.waitForFunction(() => ['loaded', 'unavailable', 'practice'].includes(SCStock.observations.facts().state));
  const hidden = (page, value) => page.evaluate(value => {
    Object.defineProperty(document, 'hidden', { configurable: true, value });
    document.dispatchEvent(new Event('visibilitychange'));
  }, value);
  const setup = async (options = {}) => {
    const endpoint = options.endpoint === undefined ? ENDPOINT : options.endpoint;
    const requests = [], response = { body: JSON.stringify(options.receipt || observed), status: 200, hold: null, headers: {} };
    const tab = await open(browser, base, '/service-publication.json', options.pinned ? NOW : null, options.width || 1280, {
      theme: options.width === 390 ? 'light' : 'dark', hash: '#/explore/bursts/AAPL', reducedMotion: 'reduce',
      beforeLoad: async (page, context) => {
        await page.clock.install({ time: new Date(options.now || NOW) });
        await page.clock.pauseAt(new Date(options.now || NOW));
        await context.addCookies([{ name: 'private_cookie', value: 'PRIVATE_SENTINEL', domain: 'receipts.example.invalid', path: '/', secure: true }]);
        await page.addInitScript(() => {
          localStorage.setItem('spicystock:morning-endpoint', 'https://private.example.invalid/morning.json?note=PRIVATE_SENTINEL');
          localStorage.setItem('private-notes', 'PRIVATE_SENTINEL off-universe ticker PRIVATESYMBOL cash 1234 broker account 999');
          window.__serviceFetches = [];
          const fetch = window.fetch;
          window.fetch = function(url, options) {
            if (String(url).includes('morning.json')) window.__serviceFetches.push({ url: String(url), credentials: options.credentials, redirect: options.redirect, mode: options.mode, referrerPolicy: options.referrerPolicy, body: options.body || null });
            return fetch.apply(this, arguments);
          };
        });
        await page.route('**/docs/index.html', route => route.fulfill({ contentType: 'text/html', body: withEndpoint(html, endpoint) }));
        await page.route('**/service-publication.json', route => route.fulfill({ contentType: 'application/json', body: options.raw || raw }));
        await page.route('**/morning.json', async route => {
          requests.push({ url: route.request().url(), method: route.request().method(), body: route.request().postData(), headers: await route.request().allHeaders() });
          const reply = { ...response };
          if (reply.hold) await reply.hold;
          await route.fulfill({ status: reply.status, contentType: 'application/json', body: reply.body, headers: { 'access-control-allow-origin': base, ...reply.headers } }).catch(() => {});
        });
      }
    });
    await wait(tab.page);
    return { ...tab, requests, response, async reload(value, status = 200) {
      response.body = typeof value === 'string' ? value : JSON.stringify(value); response.status = status;
      await tab.page.evaluate(() => SCStock.observations.reload()); await wait(tab.page);
    } };
  };

  for (const width of [1280, 390]) {
    const tab = await setup({ width }), { page } = tab;
    try {
      eq(width + ': configured receipt validates against exact publication', [(await facts(page)).state, (await facts(page)).recordHash], ['loaded', createHash('sha256').update(raw).digest('hex')]);
      await page.locator('#morning-open').click();
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('1234.');
      await page.locator('#morning-cash').focus();
      const saved = await page.evaluate(async () => {
        document.querySelector('meta[name="spicystock-morning-endpoint"]').content = 'https://changed.example.invalid/morning.json';
        return (await SCStock.follow.add({ ticker: 'PRIVATESYMBOL', kind: 'burst', session: '2026-09-10', rules_version: 'private', snapshot: { note: 'PRIVATE_SENTINEL' } })).ok;
      });
      eq(width + ': private off-universe following sentinel is actually stored', saved, true);
      tab.response.body = JSON.stringify(halted);
      await page.clock.runFor(29999);
      eq(width + ': no early automatic request', tab.requests.length, 1);
      await page.clock.runFor(2); await wait(page);
      eq(width + ': one automatic read at 30 seconds', tab.requests.length, 2);
      eq(width + ': automatic receipt changes apply their sourced halt', (await facts(page)).restricted, ['burst:AAPL']);
      eq(width + ': automatically observed halt withdraws entry copying', await page.locator('#detail [data-copy]').count(), 0);
      eq(width + ': polling preserves private cash draft and focus', await page.locator('#morning-cash').evaluate(n => [n.value, document.activeElement === n]), ['1234.', true]);
      eq(width + ': every request uses captured fixed endpoint with no private fields', tab.requests.map(r => [r.url, r.method, r.body, r.headers.cookie || null, r.headers.referer || null]), Array(2).fill([ENDPOINT, 'GET', null, null, null]));
      eq(width + ': transport refuses redirects and credentials', await page.evaluate(() => __serviceFetches), Array(2).fill({ url: ENDPOINT, credentials: 'omit', redirect: 'error', mode: 'cors', referrerPolicy: 'no-referrer', body: null }));
      check(width + ': dynamic read and failure semantics are visible', /at most once every 30 seconds/.test(await page.locator('[data-observations="summary"]').textContent()));
      eq(width + ': configured service never suggests publishing a disconnected static receipt', await page.locator('[data-observation-workflow]').count(), 0);
      await hidden(page, true); await page.clock.runFor(90000);
      eq(width + ': hidden tab stops polling', tab.requests.length, 2);
      await hidden(page, false); await page.clock.runFor(1); await wait(page);
      eq(width + ': becoming visible resumes one due read', tab.requests.length, 3);
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `morning-service-${width}.png`) });
      }
      eq(width + ': no browser errors', [...tab.errors], []);
    } finally { await tab.context.close(); }
  }

  for (const [name, options] of [
    ['static default', { endpoint: '' }], ['before pre-open', { now: '2026-09-11T12:58:00Z' }],
    ['cutoff', { now: '2026-09-11T14:00:00Z' }], ['stale session', { now: '2026-09-14T13:35:00Z' }],
    ['no admitted tickets', { raw: redRaw }], ['missing timing', { raw: JSON.stringify({ ...JSON.parse(raw), run: { ...JSON.parse(raw).run, timing: null } }) }],
    ['pinned replay', { pinned: true }], ['practice', { raw: JSON.stringify({ ...JSON.parse(raw), fixture: 'transport-practice' }) }]
  ]) {
    const tab = await setup(options);
    try {
      const initial = tab.requests.length;
      await tab.page.clock.runFor(60000);
      eq(name + ': automatic reads remain off', tab.requests.length, initial);
      if (name === 'static default') eq('empty deployment config retains exact static route', tab.requests.map(r => r.url), [base + '/docs/morning.json']);
      if (name === 'practice') eq('practice requests no receipt', initial, 0);
    } finally { await tab.context.close(); }
  }

  for (const endpoint of ['http://receipts.example.invalid/morning.json', ENDPOINT + '?ticker=AAPL', ENDPOINT + '#private', 'https://user:pass@receipts.example.invalid/morning.json', 'https://receipts.example.invalid/refresh', ENDPOINT + '?', ENDPOINT + '#', '//receipts.example.invalid/morning.json']) {
    const tab = await setup({ endpoint });
    try {
      eq('invalid endpoint refuses all network routes: ' + endpoint, [tab.requests.length, (await facts(tab.page)).state], [0, 'unavailable']);
      check('invalid endpoint explains configuration refusal', (await tab.page.locator('#disc-observations').textContent()).includes('configured morning receipt endpoint is invalid'));
    } finally { await tab.context.close(); }
  }

  const boundary = await setup({ now: '2026-09-11T12:59:45Z' });
  try {
    await boundary.page.clock.runFor(30001); await wait(boundary.page);
    eq('pre-open boundary starts polling through existing clock', boundary.requests.length, 2);
    await boundary.page.clock.pauseAt(new Date('2026-09-11T13:59:45Z'));
    await boundary.page.evaluate(() => SCStock.reclock()); await boundary.page.clock.runFor(1); await wait(boundary.page);
    const count = boundary.requests.length;
    await boundary.page.clock.runFor(60000);
    eq('cutoff cancels future automatic reads', boundary.requests.length, count);
    eq('cutoff removes entry authority', await boundary.page.evaluate(() => SCStock.avail.offered), false);
  } finally { await boundary.context.close(); }

  const retained = await setup({ receipt: halted });
  try {
    const checked = (await facts(retained.page)).generatedAt;
    for (const [name, body, status] of [
      ['malformed', '{', 200], ['outage', '{}', 503], ['omitted restriction', observed, 200],
      ['oversized', JSON.stringify({ padding: 'x'.repeat(512 * 1024) }), 200]
    ]) {
      await retained.reload(body, status);
      eq(name + ': last verified receipt and halt remain', [(await facts(retained.page)).state, (await facts(retained.page)).generatedAt, (await facts(retained.page)).restricted], ['unavailable', checked, ['burst:AAPL']]);
      eq(name + ': no static fallback', retained.requests.filter(r => r.url !== ENDPOINT), []);
    }
    await retained.page.clock.runFor(361000); await wait(retained.page);
    eq('old retained receipt remains visibly expired', (await facts(retained.page)).fresh, false);
    eq('expired restriction still withholds copying', await retained.page.locator('#detail [data-copy]').count(), 0);
  } finally { await retained.context.close(); }

  for (const [kind, phrase] of [['local_budget', 'local request budget/cadence'], ['local_backoff', 'backoff after earlier provider failure']]) {
    const deferred = structuredClone(outage);
    for (const source of Object.values(deferred.sources)) source.error_kind = kind;
    const tab = await setup({ receipt: deferred });
    try {
      eq(kind + ': local deferral is a readable unavailable-source receipt', (await facts(tab.page)).state, 'loaded');
      const detail = await tab.page.locator('#disc-observations').textContent();
      check(kind + ': no new provider request or entitlement result is claimed', detail.includes('No provider request was made in this collection: ' + phrase) && !detail.includes('This describes that request'));
      check(kind + ': unavailable quotes remain unavailable', (await tab.page.locator('#disc-observations [data-observation-quote]').textContent()).includes('bid unavailable · ask unavailable'));
      const claimedHTTP = structuredClone(deferred); claimedHTTP.sources.iex.status_code = 429;
      await tab.reload(claimedHTTP);
      eq(kind + ': skipped request cannot claim a fresh provider HTTP status', (await facts(tab.page)).state, 'unavailable');
      check(kind + ': HTTP contradiction is explained', (await tab.page.locator('#disc-observations').textContent()).includes('local deferral cannot claim a provider HTTP response'));
    } finally { await tab.context.close(); }
  }
  const malformedSource = await setup();
  try {
    for (const [name, receipt, kind] of [['unknown failure', outage, 'invented_error'], ['failure on success', observed, 'timeout'], ['unavailable without reason', outage, null]]) {
      const invalid = structuredClone(receipt); invalid.sources.iex.error_kind = kind;
      await malformedSource.reload(invalid);
      eq(name + ': contradictory source error kind is refused', (await facts(malformedSource.page)).state, 'unavailable');
      check(name + ': source failure validation explains refusal', (await malformedSource.page.locator('#disc-observations').textContent()).includes('Feed failure observation is invalid'));
    }
  } finally { await malformedSource.context.close(); }

  for (const kind of ['provider_error', 'local_backoff']) {
    const tab = await setup();
    try {
      for (const [name, modify, message] of [
        ['copied recent prices', row => { row.trade = structuredClone(observed.rows[0].trade); row.quote = structuredClone(observed.rows[0].quote); }, 'Quote availability contradicts its source'],
        ['invented comparison', row => { row.price_checks.ask = 'within_published_band'; }, 'Unavailable source claims a price comparison'],
        ['copied delayed volume', row => { row.delayed_volume = structuredClone(observed.rows[0].delayed_volume); }, 'Delayed-volume availability contradicts its source'],
        ['unavailable quote with spread', row => { row.quote.spread_usd = 0.02; }, 'Unavailable source claims quote evidence'],
        ['unavailable volume with timestamp', row => { row.delayed_volume.daily_timestamp = observed.rows[0].delayed_volume.daily_timestamp; }, 'Unavailable source claims volume evidence']
      ]) {
        const invalid = structuredClone(outage);
        for (const source of Object.values(invalid.sources)) source.error_kind = kind;
        modify(invalid.rows[0]);
        await tab.reload(invalid);
        eq(kind + '/' + name + ': source/row contradiction is refused', (await facts(tab.page)).state, 'unavailable');
        check(kind + '/' + name + ': contradiction is explained', (await tab.page.locator('#disc-observations').textContent()).includes(message));
      }
      const invalid = structuredClone(outage); invalid.sources.iex = structuredClone(observed.sources.iex);
      await tab.reload(invalid);
      check(kind + ': successful feed cannot label its data unavailable', (await tab.page.locator('#disc-observations').textContent()).includes('Quote availability contradicts its source'));
    } finally { await tab.context.close(); }
  }

  const late = await setup();
  let release;
  try {
    late.response.hold = new Promise(resolve => { release = resolve; });
    late.response.body = JSON.stringify(halted);
    await late.page.clock.runFor(30001);
    await late.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
    await late.page.evaluate(() => { for (let i = 0; i < 10; i++) { SCStock.reclock(); dispatchEvent(new Event('pageshow')); } });
    eq('clock and page-restoration bursts do not multiply inflight requests', late.requests.length, 2);
    await hidden(late.page, true);
    eq('hidden tab aborts an inflight automatic read', (await facts(late.page)).state, 'unavailable');
    release(); late.response.hold = null;
    late.response.body = JSON.stringify(resumed);
    await late.reload(resumed);
    eq('manual reload remains available while hidden', (await facts(late.page)).generatedAt, resumed.generated_at);
    await late.reload(observed);
    eq('an older otherwise valid receipt cannot replace newer evidence', (await facts(late.page)).generatedAt, resumed.generated_at);
    check('monotonic refusal names the older receipt', (await late.page.locator('#disc-observations').textContent()).includes('An older observation file was not loaded'));
    const revised = raw + '\n';
    await late.page.evaluate(raw => { const data = JSON.parse(raw); SCStock.render(data); return SCStock.observations.bind(data, raw); }, revised);
    eq('changed publication rejects previously bound quotes', [(await facts(late.page)).recordHash, (await facts(late.page)).generatedAt], [createHash('sha256').update(revised).digest('hex'), null]);
    const rebound = structuredClone(resumed); rebound.publication.data_sha256 = createHash('sha256').update(revised).digest('hex');
    await late.reload(rebound);
    eq('changed source accepts only newly bound receipt', (await facts(late.page)).generatedAt, resumed.generated_at);
  } finally { if (release) release(); await late.context.close(); }

  const redirect = await setup();
  try {
    redirect.response.headers = { location: 'https://redirect.example.invalid/morning.json' };
    await redirect.reload('{}', 302);
    eq('redirect cannot change the single configured destination', redirect.requests.map(r => r.url), [ENDPOINT, ENDPOINT]);
    eq('redirect failure preserves last verified receipt', [(await facts(redirect.page)).state, (await facts(redirect.page)).generatedAt], ['unavailable', observed.generated_at]);
  } finally { await redirect.context.close(); }

  const cutting = await setup({ now: '2026-09-11T13:59:25Z' });
  let releaseCutoff;
  try {
    cutting.response.hold = new Promise(resolve => { releaseCutoff = resolve; });
    await cutting.page.clock.runFor(30001);
    await cutting.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
    await cutting.page.clock.runFor(5000);
    eq('cutoff aborts an inflight automatic request before its ordinary timeout', [(await facts(cutting.page)).state, cutting.requests.length], ['unavailable', 2]);
  } finally { if (releaseCutoff) releaseCutoff(); await cutting.context.close(); }

  const timeout = await setup();
  let releaseTimeout;
  try {
    timeout.response.hold = new Promise(resolve => { releaseTimeout = resolve; });
    await timeout.page.clock.runFor(30001);
    await timeout.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
    await timeout.page.clock.runFor(15000); await wait(timeout.page);
    eq('configured transport keeps the 15-second request bound', [(await facts(timeout.page)).state, (await facts(timeout.page)).generatedAt], ['unavailable', observed.generated_at]);
    eq('bounded timeout does not immediately retry', timeout.requests.length, 2);
  } finally { if (releaseTimeout) releaseTimeout(); await timeout.context.close(); }
}
