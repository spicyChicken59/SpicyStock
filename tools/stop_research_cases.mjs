/* Research-only browser controls use producer-written publications and cohorts.
   Malformed cases alter served transport copies, never the stored fixtures. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DIR = path.join(ROOT, 'tests/fixtures/stop-research');
const PRIVATE = 'ZZPRIVATE-stop-research-234.56';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const ordered = value => Array.isArray(value) ? value.map(ordered) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value;
const json = value => Buffer.from(JSON.stringify(ordered(value)));
const sourceRequests = requests => requests.filter(request => /\/stop-research(?:\.json|\/)/.test(new URL(request.url).pathname));
const inspectOnly = '[data-copy], [data-order], [data-handoff-prepare], [data-follow], [data-save]';

async function file(name) {
  const raw = await readFile(path.join(DIR, name));
  return name.endsWith('.gz') ? gunzipSync(raw) : raw;
}

export async function checkStopResearch({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- stop-width research: exact publication, unchanged production authority, bounded hypothetical allocation');
  const state = page => page.evaluate(() => SCStock.stopResearch.status());
  const settled = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.stopResearch.status().state));
  const words = page => page.locator('[data-stop-body]').textContent();
  const reveal = async page => { await page.locator('[data-stop-research] > summary').click(); await settled(page); };
  const snapshot = page => page.evaluate(async () => {
    const digest = async value => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(value)))), byte => byte.toString(16).padStart(2, '0')).join('');
    const [data, model, storage] = await Promise.all([digest(SCStock.data), digest(SCStock.model), digest(localStorage)]);
    return { data, model, storage, morning: SCStock.observations.facts(),
      controls: [...document.querySelectorAll('[data-copy], [data-order], [data-handoff-prepare]')].map(node => ({
        copy: node.getAttribute('data-copy'), order: node.getAttribute('data-order'), prepare: node.hasAttribute('data-handoff-prepare'), disabled: node.disabled })) };
  });
  async function setup(fixture, options = {}) {
    const requests = [], transport = { current: options.variant || fixture, held: null, release: null };
    const tab = await open(browser, base, options.canonical ? '/stop-canonical-control.json' : null, options.now || fixture.now, options.width || 1280, {
      theme: options.theme || 'dark', reducedMotion: 'reduce', lens: 'all', hash: options.hash || '#/explore/setting-up/KE',
      beforeLoad: async (page, context) => {
        await context.addCookies([{ name: 'stop_private_cookie', value: PRIVATE, url: base }]);
        page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData(), headers: request.headers() }));
        await page.addInitScript(privateValue => {
          localStorage.setItem('stop-research-private-sentinel', privateValue);
          window.__stopRequests = [];
          const fetch = window.fetch;
          window.fetch = function(url, options = {}) {
            if (/\/stop-research(?:\.json|\/)/.test(String(url))) window.__stopRequests.push({ url: String(url),
              credentials: options.credentials, mode: options.mode, redirect: options.redirect,
              referrerPolicy: options.referrerPolicy, body: options.body || null, method: options.method || 'GET' });
            return fetch.apply(this, arguments);
          };
        }, PRIVATE);
        await page.route('**/docs/reader.json', route => route.fulfill({ contentType: 'application/json', body: fixture.reader }));
        await page.route('**/stop-canonical-control.json', route => route.fulfill({ contentType: 'application/json', body: fixture.publication }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: '{}' }));
        await page.route('**/stop-research.json', async route => {
          const current = transport.current;
          if (transport.held === 'receipt') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ status: current.receiptStatus || 200, contentType: 'application/json', body: typeof current.receipt === 'string' ? current.receipt : JSON.stringify(current.receipt) });
        });
        await page.route('**/stop-research/*.json', async route => {
          const current = transport.current;
          if (transport.held === 'bundle') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ status: current.bundleStatus || 200, contentType: 'application/json', body: current.raw });
        });
        if (options.beforeLoad) await options.beforeLoad(page, context);
      }
    });
    await tab.page.waitForFunction(() => SCStock.stopResearch && !!SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    await tab.page.locator('#morning-open').click();
    return { ...tab, requests, transport };
  }

  async function fixture(name) {
    const [publication, reader, receiptRaw, raw] = await Promise.all([
      file(name + '-publication.json.gz'), file(name + '-reader.json.gz'),
      file(name + '-receipt.json'), file(name + '-bundle.json')
    ]);
    const receipt = JSON.parse(receiptRaw);
    return { publication, reader, receipt, raw, now: new Date(Date.parse(receipt.timing.generated_at) + 60000).toISOString() };
  }
  const current = await fixture('current'), currentBundle = JSON.parse(current.raw);
  function changed(edit) {
    const receipt = structuredClone(current.receipt), bundle = structuredClone(currentBundle);
    edit(receipt, bundle);
    const raw = json(bundle);
    receipt.bundle = { sha256: sha(raw), bytes: raw.length, path: 'stop-research/' + sha(raw) + '.json' };
    return { receipt, raw };
  }
  const common = (key, value) => changed((receipt, bundle) => { receipt[key] = value; bundle[key] = structuredClone(value); });
  const binding = (key, value) => common('publication', { ...current.receipt.publication, [key]: value });
  const row = (bundle, ticker) => bundle.rows.find(candidate => candidate.ticker === ticker);
  const rowText = (page, ticker) => page.locator('[data-stop-row="' + ticker + '"]').textContent();
  const value = (page, key, ticker) => page.locator((ticker ? '[data-stop-row="' + ticker + '"] ' : '[data-stop-body] ') + '[data-stop-value="' + key + '"]').textContent();
  const noActions = async (page, label) => {
    eq(label + ': research exposes no order/copy/prepare/save action', await page.locator('[data-stop-research]').locator(inspectOnly).count(), 0);
  };
  const fit = async (page, label) => check(label + ': research fits the dialog and page', await page.locator('#morning-desk').evaluate(host => host.scrollWidth <= host.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
  const capture = async (page, name) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true });
    await page.locator('[data-stop-status]').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(shotsDir, name + '.png') });
    if (await page.locator('[data-stop-row="KE"]').count()) {
      await page.locator('[data-stop-row="KE"]').evaluate(node => node.scrollIntoView({ block: 'start' }));
      await page.screenshot({ path: path.join(shotsDir, name + '-KE.png') });
    }
  };

  for (const [width, theme, canonical] of [[1280, 'dark', false], [390, 'light', false], [390, 'dark', true], [1280, 'light', true]]) {
    const label = width + '/' + theme, tab = await setup(current, { width, theme, canonical });
    const { page, context, requests, errors } = tab;
    try {
      eq(label + ': closed comparison performs zero research requests', sourceRequests(requests).length, 0);
      eq(label + ': actual publication bytes are bound', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(canonical ? current.publication : current.reader));
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('234.56'); await page.locator('#morning-cash').focus();
      const before = await snapshot(page);
      const requestsBeforeResearch = requests.length;
      await page.evaluate(() => {
        window.__stopCashNode = document.getElementById('morning-cash');
        window.__stopChartNode = document.querySelector('#detail .sc-chart svg');
        document.querySelector('[data-stop-research]').open = true;
      });
      await settled(page);
      eq(label + ': genuine producer research loads', (await state(page)).state, 'loaded');
      eq(label + ': every original top row remains in rank order', await page.locator('[data-stop-row]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-stop-row'))), ['MG', 'KE', 'ZIM', 'SN', 'PSNL']);
      eq(label + ': private cash node, value and focus survive load', await page.evaluate(() => [document.getElementById('morning-cash') === window.__stopCashNode, window.__stopCashNode.value, document.activeElement === window.__stopCashNode]), [true, '234.56', true]);
      eq(label + ': a non-null actual chart is preserved', await page.evaluate(() => !!window.__stopChartNode && document.querySelector('#detail .sc-chart svg') === window.__stopChartNode), true);
      eq(label + ': research cannot mutate publication, model, storage, orders or morning authority', await snapshot(page), before);
      await noActions(page, label);
      const text = await words(page);
      check(label + ': experiment is labelled as research with its fixed dates', /research/i.test(text) && /2026-10-12/.test(text) && /2026-11-06/.test(text));
      for (const [ticker, shares, principal, risk, trigger, limit, stop] of [
        ['KE', '1', '$29.52', '$1.27', '$29.23', '$29.52', '$28.25'],
        ['PSNL', '3', '$49.26', '$2.22', '$16.26', '$16.42', '$15.68']
      ]) {
        eq(label + ': ' + ticker + ' independently sized hypothetical shares', await value(page, 'research-shares', ticker), shares);
        eq(label + ': ' + ticker + ' admitted only to research allocation', await value(page, 'allocated-shares', ticker), shares);
        eq(label + ': ' + ticker + ' limit principal', await value(page, 'research-row-principal', ticker), principal);
        eq(label + ': ' + ticker + ' gross price-to-stop risk', await value(page, 'research-row-risk', ticker), risk);
        eq(label + ': ' + ticker + ' reduced effective risk budget', await value(page, 'risk-budget', ticker), '$2.50');
        eq(label + ': ' + ticker + ' keeps original structural geometry', await Promise.all(['trigger', 'limit', 'stop'].map(key => value(page, key, ticker))), [trigger, limit, stop]);
        check(label + ': ' + ticker + ' production refusal remains clear', /No production ticket/.test(await rowText(page, ticker)));
      }
      eq(label + ': aggregate hypothetical principal', await value(page, 'research-principal'), '$78.78');
      eq(label + ': aggregate hypothetical price-to-stop risk', await value(page, 'research-risk'), '$3.49');
      eq(label + ': shared model slots include the unfinished SN plan', await value(page, 'slots-used'), '3 of 4');
      eq(label + ': shared principal retains the unfinished SN reservation', await value(page, 'remaining-principal'), '$1,732.85');
      check(label + ': existing SN remains occupied and cannot afford one share', /already occupies|occupied|unfinished model plan/i.test(await rowText(page, 'SN')) && /whole share/i.test(await rowText(page, 'SN')));
      check(label + ': both recorded acquisition exclusions remain explicit', /event|acquisition/i.test(await rowText(page, 'MG')) && /event|acquisition/i.test(await rowText(page, 'ZIM')));
      check(label + ': actual fees, gaps, slippage and unverified broker cash remain limitations', /fees/i.test(text) && /gaps/i.test(text) && /slippage/i.test(text) && /broker/i.test(text));
      check(label + ': missing quote, issuer-news and earnings coverage is explicit', /quote/i.test(text) && /news/i.test(text) && /earnings/i.test(text));
      eq(label + ': only the fixed receipt and exact digest path are fetched', sourceRequests(requests).map(request => new URL(request.url).pathname), ['/docs/stop-research.json', '/docs/' + current.receipt.bundle.path]);
      eq(label + ': opening research makes no provider or private-symbol request', requests.slice(requestsBeforeResearch).map(request => request.url), sourceRequests(requests).map(request => request.url));
      check(label + ': transport cannot carry cookies, private input, bodies or symbols', sourceRequests(requests).every(request => request.method === 'GET' && !request.body && !request.headers.cookie && !request.headers.referer && !request.url.includes(PRIVATE) && !request.url.includes('234.56') && !new URL(request.url).search));
      check(label + ': transport explicitly omits credentials/referrer and refuses redirects', (await page.evaluate(() => window.__stopRequests)).every(request => request.credentials === 'omit' && request.referrerPolicy === 'no-referrer' && request.mode === 'same-origin' && request.redirect === 'error' && request.body === null));
      await fit(page, label); await capture(page, 'stop-research-' + width + '-' + theme);
      eq(label + ': valid research causes no browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  const boundary = await setup(current);
  try {
    const { page, transport } = boundary;
    await reveal(page);
    eq('boundary control first loads the genuine cohort', (await state(page)).state, 'loaded');
    const original = await snapshot(page);
    const mutateRow = edit => changed((receipt, bundle) => edit(row(bundle, 'KE'), bundle, receipt));
    const cases = [
      ['canonical bytes', binding('data_sha256', '0'.repeat(64))],
      ['actual reader bytes', binding('reader_sha256', current.receipt.publication.data_sha256)],
      ['context digest', binding('context_sha256', '0'.repeat(64))],
      ['run identity', binding('run_id', 'different-source-run')],
      ['rules identity', binding('rules_version', 'f'.repeat(12))],
      ['published timestamp', binding('published_at', '2026-10-10T07:00:00Z')],
      ['measured session', binding('measured_session', '2026-10-08')],
      ['applicable session', binding('applicable_session', '2026-10-13')],
      ['projection version', binding('reader_projection_version', 2)],
      ['supported stop cap', common('policy', { ...current.receipt.policy, research_stop_pct: 6 })],
      ['supported account', common('policy', { ...current.receipt.policy, account: { ...current.receipt.policy.account, equity: 10000 } })],
      ['fixed registered period', common('policy', { ...current.receipt.policy, applicable_end: '2026-12-31' })],
      ['baseline-first policy', common('policy', { ...current.receipt.policy, allocation: 'research_first' })],
      ['entry timing', common('timing', { ...current.receipt.timing, entry_cutoff_at: '2026-10-12T14:01:00Z' })],
      ['future generation', common('timing', { ...current.receipt.timing, generated_at: '2026-10-11T12:00:00Z' })],
      ['source evidence ID', mutateRow(candidate => { candidate.evidence.id = '0'.repeat(64); })],
      ['original plan ID', mutateRow(candidate => { candidate.evidence.plan_sha256 = '0'.repeat(64); })],
      ['source bars ID', mutateRow(candidate => { candidate.evidence.source_sha256 = '0'.repeat(64); })],
      ['original row rank', mutateRow(candidate => { candidate.rank = 1; })],
      ['unchanged structural stop', mutateRow(candidate => { candidate.levels.stop -= 0.01; })],
      ['unchanged trigger', mutateRow(candidate => { candidate.levels.trigger -= 0.01; })],
      ['original baseline refusal', mutateRow(candidate => { candidate.baseline.admitted = true; })],
      ['whole shares', mutateRow(candidate => { candidate.research.shares = 1.5; })],
      ['principal arithmetic', mutateRow((candidate, bundle) => {
        candidate.research.principal_usd += 0.01; bundle.reservations.research_principal_usd += 0.01; bundle.reservations.remaining_model_principal_usd -= 0.01;
      })],
      ['price-to-stop arithmetic', mutateRow((candidate, bundle) => { candidate.research.risk_usd += 0.01; bundle.reservations.research_risk_usd += 0.01; })],
      ['effective risk budget', mutateRow(candidate => { candidate.research.effective_risk_budget_usd = 10; })],
      ['risk reduction multiplier', mutateRow(candidate => { candidate.research.multipliers.stop_risk = 1; })],
      ['event registry identity', mutateRow(candidate => { candidate.event.registry_sha256 = '0'.repeat(64); })],
      ['source session', mutateRow(candidate => { candidate.quality.source_session = '2026-10-08'; })],
      ['no executable research field', mutateRow(candidate => { candidate.order_json = { symbol: 'KE', quantity: 1 }; })],
      ['remaining model principal', changed((receipt, bundle) => { bundle.reservations.remaining_model_principal_usd += 0.01; })],
      ['preserved open-model reservation', changed((receipt, bundle) => { bundle.reservations.open_model_principal_usd = 0; })],
      ['complete cohort membership', changed((receipt, bundle) => { bundle.rows.pop(); })],
      ['required coverage limits', changed((receipt, bundle) => { bundle.limits = []; })]
    ];
    for (const [name, variant] of cases) {
      transport.current = variant; await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
      eq(name + ': independently resealed malformed transport is refused', (await state(page)).state, 'unavailable');
      eq(name + ': no previous or invalid hypothetical rows survive', await page.locator('[data-stop-row]').count(), 0);
      eq(name + ': production and private state remain untouched', await snapshot(page), original);
    }
    for (const [name, edit] of [
      ['path traversal', receipt => { receipt.bundle.path = '../private.json'; }],
      ['cross-origin path', receipt => { receipt.bundle.path = 'https://example.com/private.json'; }],
      ['oversized declared bundle', receipt => { receipt.bundle.bytes = 128 * 1024 + 1; }],
      ['different raw digest', receipt => { receipt.bundle.sha256 = '0'.repeat(64); receipt.bundle.path = 'stop-research/' + receipt.bundle.sha256 + '.json'; }],
      ['truncated declared length', receipt => { receipt.bundle.bytes -= 1; }]
    ]) {
      const receipt = structuredClone(current.receipt); edit(receipt);
      transport.current = { receipt, raw: current.raw };
      await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
      eq(name + ': transport cannot attach', (await state(page)).state, 'unavailable');
      eq(name + ': no research rows appear', await page.locator('[data-stop-row]').count(), 0);
    }
    const bom = { receipt: structuredClone(current.receipt), raw: Buffer.concat([Buffer.from([239, 187, 191]), current.raw]) };
    bom.receipt.bundle.bytes = bom.raw.length;
    transport.current = bom; await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
    eq('raw BOM bytes cannot masquerade as the expected cohort', (await state(page)).state, 'unavailable');
    check('BOM control fails its exact raw digest boundary', /digest differs/.test((await state(page)).issue));
    transport.current = { receipt: ' '.repeat(16 * 1024 + 1), raw: current.raw };
    await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
    check('actual receipt byte cap precedes JSON parsing', /size limit|declared size/.test((await state(page)).issue));
    await page.evaluate(() => {
      window.__stopNormalFetch = window.fetch;
      window.fetch = async function(url, options) {
        const response = await window.__stopNormalFetch.apply(this, arguments);
        const pathname = new URL(url, location.href).pathname;
        const cap = window.__stopOversize === 'receipt' && pathname.endsWith('/stop-research.json') ? 16 * 1024
          : window.__stopOversize === 'bundle' && /\/stop-research\/[a-f0-9]{64}\.json$/.test(pathname) ? 128 * 1024 : null;
        if (cap === null) return response;
        await response.arrayBuffer();
        return new Response(new ReadableStream({ start(controller) {
          controller.enqueue(new Uint8Array(cap)); controller.enqueue(new Uint8Array(1)); controller.close();
        } }), { headers: { 'content-length': '1' } });
      };
    });
    for (const role of ['receipt', 'bundle']) {
      transport.current = { ...current, receipt: structuredClone(current.receipt) };
      if (role === 'bundle') transport.current.receipt.bundle.bytes = 128 * 1024;
      await page.evaluate(role => { window.__stopOversize = role; return SCStock.stopResearch.reload(); }, role);
      await settled(page);
      check(role + ': actual streamed cap rejects bytes despite a false small content-length', /exceeds its declared size/.test((await state(page)).issue));
      eq(role + ': oversized stream never renders hypothetical rows', await page.locator('[data-stop-row]').count(), 0);
    }
    await page.evaluate(() => { window.fetch = window.__stopNormalFetch; });
    for (const role of ['receipt', 'bundle']) {
      transport.current = { ...current, [role + 'Status']: 404 };
      await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
      eq(role + ': a missing optional publication is unavailable', (await state(page)).state, 'unavailable');
      eq(role + ': outage preserves production and private state', await snapshot(page), original);
      eq(role + ': outage clears prior hypothetical rows', await page.locator('[data-stop-row]').count(), 0);
      await noActions(page, role + ' outage');
    }
    transport.current = current; await page.evaluate(() => SCStock.stopResearch.reload()); await settled(page);
    eq('explicit retry recovers the exact original after malformed transports', (await state(page)).state, 'loaded');
    await page.evaluate(() => { SCStock.now = '2026-10-12T14:01:00Z'; SCStock.stopResearch.update(SCStock.data); });
    check('ended entry window leaves an explicitly archived comparison', /archived|after entry/i.test(await page.locator('[data-stop-status]').textContent()));
    await noActions(page, 'ended entry window');
    await page.evaluate(() => { SCStock.now = '2026-11-09T15:00:00Z'; SCStock.reclock(); SCStock.stopResearch.update(SCStock.data); });
    check('stale publication cannot look like current trading research', /archived|stale/i.test(await page.locator('[data-stop-status]').textContent()));
    await noActions(page, 'stale publication');
    eq('handled invalid transports and optional-source outages produce no page exceptions', [...boundary.errors], []);
  } finally { await boundary.context.close(); }

  for (const name of ['empty', 'red', 'outside', 'priority']) {
    const source = await fixture(name), bundle = JSON.parse(source.raw);
    const tab = await setup(source, { hash: '#/explore', width: 390, theme: 'light' });
    try {
      const before = await snapshot(tab.page);
      await reveal(tab.page);
      eq(name + ': real producer cohort remains readable', (await state(tab.page)).state, 'loaded');
      eq(name + ': exact complete membership remains', await tab.page.locator('[data-stop-row]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-stop-row'))), bundle.rows.map(candidate => candidate.ticker));
      if ((await state(tab.page)).state !== 'loaded') continue;
      if (name === 'empty') {
        eq('empty cohort is recorded rather than an unavailable source', bundle.status, 'recorded');
        check('zero top rows are explicitly retained as a cohort', /Zero-row cohort/.test(await words(tab.page)));
        eq('empty cohort allocates no hypothetical shares', await value(tab.page, 'allocation-fit'), '0');
      } else if (name === 'red') {
        eq('red-market research never gains allocation', await value(tab.page, 'allocation-fit'), '0');
        check('red-market refusal remains visible with its source rows', /market regime refuses/.test(await words(tab.page)));
      } else if (name === 'outside') {
        eq('outside-period record has no registered experiment rows', await tab.page.locator('[data-stop-row]').count(), 0);
        check('outside-period scope is clearly labelled', /Outside the registered period/.test(await words(tab.page)));
      } else {
        eq('priority control contains the actual unchanged lower-ranked production ticket', bundle.reservations.baseline_symbols, ['ZBASE']);
        eq('unchanged baseline ZBASE retains its published share', await value(tab.page, 'baseline-shares', 'ZBASE'), '1');
        check('unchanged baseline ZBASE remains explicitly a production ticket', /Production ticket retained/.test(await rowText(tab.page, 'ZBASE')));
        eq('baseline reservation leaves only three hypothetical slots', await value(tab.page, 'allocation-fit'), '3');
        eq('first three research rows use original watchlist rank', await Promise.all(['COIL', 'RONE', 'RTHR'].map(ticker => value(tab.page, 'allocated-shares', ticker))), ['1', '1', '1']);
        eq('fourth research row cannot displace lower-ranked baseline', await value(tab.page, 'allocated-shares', 'RTWO'), '0');
        check('fourth research row explains the occupied slot budget', /No model position slot remains/.test(await rowText(tab.page, 'RTWO')));
        eq('priority preserves baseline principal before allocating research', await value(tab.page, 'remaining-principal'), '$1,719.19');
        check('priority control explicitly preserves baseline before research', /unchanged production tickets reserve/.test(await words(tab.page)) && /Research cannot displace/.test(await words(tab.page)));
      }
      eq(name + ': no publication/private/order mutation', await snapshot(tab.page), before);
      await noActions(tab.page, name); await fit(tab.page, name);
      await capture(tab.page, 'stop-research-' + name + '-390-light');
      eq(name + ': valid comparison has no browser errors', [...tab.errors], []);
    } finally { await tab.context.close(); }
  }

  const late = { ...current, receipt: JSON.parse(await file('current-late-receipt.json')), raw: await file('current-late-bundle.json') };
  late.now = new Date(Date.parse(late.receipt.timing.generated_at) + 60000).toISOString();
  const lateTab = await setup(late);
  try {
    await reveal(lateTab.page);
    eq('actual late producer comparison remains readable research', (await state(lateTab.page)).state, 'loaded');
    check('late generation is explicitly after entry, never called prospective', /recorded after|after entry/i.test(await lateTab.page.locator('[data-stop-status]').textContent()));
    await noActions(lateTab.page, 'actual after-entry collection');
  } finally { await lateTab.context.close(); }

  const replacement = await fixture('empty'), race = await setup(current);
  try {
    race.transport.held = 'bundle';
    await race.page.locator('[data-stop-research] > summary').click();
    for (let i = 0; i < 100 && !race.transport.release; i++) await race.page.waitForTimeout(20);
    check('late-response control holds a real requested old bundle', !!race.transport.release);
    await race.page.evaluate(async raw => {
      const next = JSON.parse(raw); SCStock.render(next, new Date(SCStock.now)); await SCStock.observations.bind(next, raw);
    }, replacement.publication.toString('utf8'));
    const release = race.transport.release; race.transport.held = null;
    if (release) release();
    await settled(race.page);
    eq('late old research cannot attach to a replacement publication', (await state(race.page)).state, 'unavailable');
    eq('late old hypothetical quantities stay absent', await race.page.locator('[data-stop-row]').count(), 0);
    eq('replacement exact canonical hash remains authoritative', await race.page.evaluate(() => SCStock.observations.facts().canonicalHash), sha(replacement.publication));
  } finally { if (race.transport.release) race.transport.release(); await race.context.close(); }

  const cryptoTab = await setup(current);
  try {
    await cryptoTab.page.evaluate(() => Object.defineProperty(window, 'crypto', { configurable: true, value: undefined }));
    await reveal(cryptoTab.page);
    eq('missing exact-byte verification refuses research', (await state(cryptoTab.page)).state, 'unavailable');
    eq('missing crypto makes zero unverified source requests', sourceRequests(cryptoTab.requests).length, 0);
    await noActions(cryptoTab.page, 'missing crypto');
  } finally { await cryptoTab.context.close(); }
}
