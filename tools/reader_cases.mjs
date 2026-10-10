/* Compact-reader acceptance over real backend-derived offline publications.
   Malformed transport bytes and private local saves are labelled boundary
   controls; no fixture is represented as a production recommendation. */
import { readFile, mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-11T13:35:00Z';
const PAGE_NOW = '2026-09-11T22:31:00Z';
const PRIVATE = 'ZZPRIVATE';
const sha = raw => createHash('sha256').update(raw).digest('hex');
const python = process.env.SCSTOCK_PYTHON || 'python';

function derive(raw) {
  const encoded = execFileSync(python, ['-c', [
    'import base64,json,sys', 'from src.reader import derive',
    'reader,observations=derive(sys.stdin.buffer.read())',
    'print(json.dumps([base64.b64encode(reader).decode(),base64.b64encode(observations).decode()]))'
  ].join('\n')], { cwd: ROOT, input: raw, maxBuffer: 64 * 1024 * 1024 });
  const [reader, observations] = JSON.parse(encoded);
  return bundle(Buffer.from(reader, 'base64').toString('utf8'), Buffer.from(observations, 'base64'), raw);
}

function bundle(readerRaw, sidecarRaw, canonicalRaw = null) {
  const envelope = JSON.parse(readerRaw);
  return { readerRaw, sidecarRaw, canonicalRaw, envelope,
    data: canonicalRaw ? JSON.parse(canonicalRaw) : null,
    sidecarPath: '/docs/' + envelope.retained_observations.path };
}

function changedSidecar(original, value) {
  const raw = Buffer.from(JSON.stringify(value));
  const envelope = structuredClone(original.envelope);
  envelope.retained_observations = { sha256: sha(raw), bytes: raw.length,
    path: 'reader-observations/' + sha(raw) + '.json' };
  return bundle(JSON.stringify(envelope), raw, original.canonicalRaw);
}

export async function checkReaderTransport({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- compact reader: exact bytes, deferred research, private saves and receipt binding');
  const canonical = await readFile(path.join(ROOT, 'tests/fixtures/morning/full-publication.json'));
  const production = derive(await readFile(path.join(ROOT, 'docs/data.json')));
  const morning = derive(canonical);
  const full = derive(await readFile(path.join(ROOT, 'tests/fixtures/page/full.json')));
  const next = derive(await readFile(path.join(ROOT, 'tests/fixtures/page/next.json')));
  const revised = derive(await readFile(path.join(ROOT, 'tests/fixtures/page/revised.json')));
  const receipt = async name => JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning', name + '.json')));
  const observed = await receipt('reader-observed');
  const readerState = page => page.evaluate(() => SCStock.reader.status());
  const waitResearch = (page, state) => page.waitForFunction(want => SCStock.reader.status().state === want, state);
  const waitMorning = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.observations.facts().state));
  const checkSame = (name, actual, expected) => check(name, isDeepStrictEqual(actual, expected));

  async function setup(initial, options = {}) {
    const requests = [], sidecars = [], transport = { current: initial, receipt: options.receipt || null, sidecar: options.sidecar || null };
    const tab = await open(browser, base, options.canonical ? '/reader-canonical-control.json' : null,
      options.now || NOW, options.width || 1280, {
        theme: options.theme || 'dark', lens: 'all', reducedMotion: 'reduce',
        hash: options.hash || '#/explore/bursts/AAPL',
        beforeLoad: async (page, context) => {
          await context.addCookies([{ name: 'reader_private_cookie', value: PRIVATE, url: base }]);
          page.on('request', request => requests.push({ url: request.url(), method: request.method(),
            body: request.postData(), headers: request.headers() }));
          await page.addInitScript(({ seed }) => {
            window.__readerFetches = [];
            const original = window.fetch;
            window.fetch = function(url, options = {}) {
              if (String(url).includes('reader-observations/')) window.__readerFetches.push({
                url: String(url), credentials: options.credentials, referrerPolicy: options.referrerPolicy,
                mode: options.mode, redirect: options.redirect, method: options.method || 'GET', body: options.body || null
              });
              return original.apply(this, arguments);
            };
            window.__readerFirstRender = null;
            const observer = new MutationObserver(() => {
              if (document.documentElement.hasAttribute('data-ss-rendered') && window.__readerFirstRender === null) {
                window.__readerFirstRender = performance.now(); observer.disconnect();
              }
            });
            observer.observe(document, { attributes: true, subtree: true });
            if (seed) Object.entries(seed).forEach(([key, value]) => localStorage.setItem(key, value));
          }, { seed: options.seed || null });
          await page.route('**/reader.json*', route => route.fulfill({ contentType: 'application/json', body: transport.current.readerRaw }));
          await page.route('**/reader-canonical-control.json*', route => route.fulfill({ contentType: 'application/json', body: initial.canonicalRaw }));
          await page.route('**/docs/data.json', route => route.fulfill({ status: 500, body: 'Canonical request forbidden in compact-reader control.' }));
          await page.route('**/reader-observations/*.json', async route => {
            sidecars.push(route.request().url());
            if (transport.sidecar) return transport.sidecar(route, transport);
            await route.fulfill({ contentType: 'application/json', body: transport.current.sidecarRaw });
          });
          await page.route('**/morning.json', route => transport.receipt
            ? route.fulfill({ contentType: 'application/json', body: JSON.stringify(transport.receipt) })
            : route.fulfill({ status: 404, body: 'No matching receipt in this transport-only control.' }));
          await page.route('https://api.github.com/**', route => route.abort());
          if (options.beforeLoad) await options.beforeLoad(page, context);
        }
      });
    return { ...tab, requests, sidecars, transport };
  }

  // Actual production-sized bytes establish the default load and first-decision
  // cost. No source fields are changed to make the live record offer an order.
  for (const width of [1280, 390]) {
    const tab = await setup(production, { width, now: production.data.generated || NOW });
    try {
      eq(`${width}: default request loads reader.json`, tab.requests.filter(r => new URL(r.url).pathname === '/docs/reader.json').length, 1);
      eq(`${width}: morning load requests no canonical record`, tab.requests.filter(r => new URL(r.url).pathname === '/docs/data.json').length, 0);
      eq(`${width}: morning load requests no observation sidecar`, tab.sidecars.length, 0);
      eq(`${width}: morning load requests no historical findings`, tab.requests.filter(r => /historical-(findings|validation)\.json/.test(r.url)).length, 0);
      eq(`${width}: deferred research is explicit internally`, (await readerState(tab.page)).state, 'deferred');
      eq(`${width}: deferred research does not invent missing symbols`, await tab.page.evaluate(() => Object.keys(SCStock.data.observations.symbols).length), 0);
      await tab.page.locator('#morning-open').click();
      check(`${width}: first morning decision is readable`, (await tab.page.locator('#morning-desk [data-morning="headline"]').textContent()).trim().length > 0);
      check(`${width}: morning desk fits viewport`, await tab.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const timing = await tab.page.evaluate(() => ({ firstRenderMs: window.__readerFirstRender,
        resources: performance.getEntriesByType('resource').filter(r => /reader\.json$/.test(r.name)).map(r => ({ transferSize: r.transferSize, encodedBodySize: r.encodedBodySize, decodedBodySize: r.decodedBodySize })) }));
      console.log('reader measurement ' + JSON.stringify({ width, canonicalBytes: production.canonicalRaw.length,
        readerBytes: Buffer.byteLength(production.readerRaw), sidecarBytes: production.sidecarRaw.length,
        transport: 'local uncompressed Playwright route; not a Pages compression measurement', ...timing }));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await tab.page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `reader-morning-${width}.png`) });
      }
      eq(`${width}: production-size reader runtime errors`, [...tab.errors], []);
    } finally { await tab.context.close(); }
  }

  // Save an original through the real UI, then carry that private store into
  // later backend publications. The separate off-universe save is local input.
  let savedSeed, savedOriginal;
  {
    const tab = await setup(full, { canonical: true, now: '2026-09-10T22:31:00Z' });
    try {
      eq('canonical dataUrl callers remain supported', (await readerState(tab.page)).projected, false);
      await tab.page.locator('#detail [data-follow-action="add"]').click();
      await tab.page.waitForFunction(() => SCStock.follow.list().some(item => item.ticker === 'AAPL'));
      await tab.page.locator('#detail [data-select-plan]').click();
      await tab.page.waitForFunction(() => SCStock.follow.list().some(item => item.ticker === 'AAPL' && item.plan_selection));
      savedOriginal = await tab.page.evaluate(() => SCStock.follow.list().find(item => item.ticker === 'AAPL'));
      savedSeed = await tab.page.evaluate(() => Object.fromEntries(Object.keys(localStorage).filter(key => key.includes('following')).map(key => [key, localStorage.getItem(key)])));
      await tab.page.evaluate(record => SCStock.render(record), full.data);
      checkSame('direct SCStock.render retains canonical callers', await tab.page.evaluate(() => SCStock.data), full.data);
    } finally { await tab.context.close(); }
  }
  const privateSeed = structuredClone(savedSeed);
  for (const [key, raw] of Object.entries(privateSeed)) {
    if (key !== 'spicystock:following:demo:v1') continue;
    const store = JSON.parse(raw), item = structuredClone(savedOriginal);
    item.ticker = PRIVATE; item.id = ['burst', PRIVATE, item.session, item.rules_version].join(':');
    item.snapshot.name = 'Local private boundary control';
    store.items.push(item); privateSeed[key] = JSON.stringify(store);
  }

  for (const basis of ['match', 'adjusted']) {
    const seed = structuredClone(privateSeed);
    if (basis === 'adjusted') {
      // Alter only a private saved original to model an earlier price basis;
      // the public pipeline record and sidecar remain byte-for-byte unchanged.
      const key = 'spicystock:following:demo:v1', store = JSON.parse(seed[key]);
      const item = store.items.find(item => item.ticker === 'AAPL');
      item.snapshot.close *= 2;
      for (const bar of item.evidence.series) for (const field of ['o', 'h', 'l', 'c']) bar[field] *= 2;
      seed[key] = JSON.stringify(store);
    }
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const tab = await setup(next, { seed, now: PAGE_NOW, sidecar: async route => {
      await gate; await route.fulfill({ contentType: 'application/json', body: next.sidecarRaw }).catch(() => {});
    } });
    try {
      const untouched = await tab.page.evaluate(() => SCStock.follow.list().find(item => item.ticker === 'AAPL'));
      eq(`${basis}: no incomplete fallback bars merge before hydration`, untouched.observations, savedOriginal.observations);
      await tab.page.evaluate(() => SCStock.navigate('#/setups'));
      await waitResearch(tab.page, 'loading');
      const loading = await tab.page.locator('#view-setups').textContent();
      check(`${basis}: loading coverage does not assert absent public data`, /loading/i.test(loading) && !/not observed in the loaded record|tonight.s included/i.test(loading));
      release(); await waitResearch(tab.page, 'complete');
      await tab.page.waitForFunction(() => SCStock.follow.list().find(item => item.ticker === 'AAPL').observations.length > 0);
      const saved = await tab.page.evaluate(() => SCStock.follow.list().find(item => item.ticker === 'AAPL'));
      eq(`${basis}: verified history establishes saved-bar basis`, saved.observations.at(-1).basis, basis);
      eq(`${basis}: observation comes from the retained public sidecar`, saved.observations.at(-1).c, next.data.observations.symbols.AAPL.c);
      checkSame(`${basis}: hydration recovers the exact canonical publication`, await tab.page.evaluate(() => SCStock.data), next.data);
      checkSame(`${basis}: original saved chart remains unchanged`, saved.evidence, untouched.evidence);
      const count = tab.sidecars.length;
      await tab.page.evaluate(() => Promise.all([SCStock.reader.ensure(), SCStock.reader.ensure()]));
      eq(`${basis}: successful shared sidecar is loaded once`, tab.sidecars.length, count);
      const fetches = await tab.page.evaluate(() => window.__readerFetches);
      check(`${basis}: sidecar uses only a shared public digest path`, fetches.every(r => /\/reader-observations\/[a-f0-9]{64}\.json$/.test(r.url) && r.credentials === 'omit' && r.referrerPolicy === 'no-referrer' && r.mode === 'same-origin' && r.redirect === 'error' && r.method === 'GET' && r.body === null));
      const researchRequests = tab.requests.filter(r => /reader-observations/.test(r.url));
      check(`${basis}: no private ticker, cookie or annotation leaves in research request`, researchRequests.every(r => !JSON.stringify(r).includes(PRIVATE) && !r.headers.cookie && !r.headers.referer));
      if (shotsDir && basis === 'adjusted') await tab.page.locator('#view-setups').screenshot({ path: path.join(shotsDir, 'reader-saved-adjustment.png') });
      eq(`${basis}: hydration runtime errors`, [...tab.errors], []);
    } finally { release(); await tab.context.close(); }
  }

  // A real selected-plan sequel remains readable while only bulk price
  // research is deferred. Completing research must not rebuild the saved
  // original chart or disrupt an annotation still being typed.
  {
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const tab = await setup(next, { seed: savedSeed, now: PAGE_NOW, sidecar: async route => {
      await gate; await route.fulfill({ contentType: 'application/json', body: next.sidecarRaw }).catch(() => {});
    } });
    try {
      const model = await tab.page.evaluate(() => SCStock.follow.list().find(item => item.ticker === 'AAPL').model_observation);
      eq('exact model outcome is retained before price research loads', [model.row.status, model.row.evidence_ref.id], ['stopped', savedOriginal.plan_selection.reference.id]);
      await tab.page.evaluate(id => SCStock.navigate('#/followed/' + encodeURIComponent(id)), savedOriginal.id);
      await waitResearch(tab.page, 'loading');
      await tab.page.locator('#saved').waitFor({ state: 'visible' });
      check('deferred saved detail displays the exact dated model outcome', /STOPPED/.test(await tab.page.locator('#saved [data-model-update="matched"]').textContent()));
      await tab.page.locator('#setup-amount').fill('125.');
      await tab.page.locator('#setup-amount').focus();
      const mounted = await tab.page.evaluate(() => {
        window.__savedChart = document.querySelector('#saved-mount > [data-sessions]');
        window.__savedAmount = document.getElementById('setup-amount');
        return !!window.__savedChart && !!window.__savedAmount;
      });
      check('saved hydration control captures a real chart and annotation node', mounted);
      release(); await waitResearch(tab.page, 'complete');
      await tab.page.waitForFunction(() => document.querySelector('#saved [data-obs-row]'));
      eq('saved-sheet hydration keeps original chart and annotation nodes', await tab.page.evaluate(() => [
        window.__savedChart === document.querySelector('#saved-mount > [data-sessions]'),
        window.__savedAmount === document.getElementById('setup-amount')
      ]), [true, true]);
      eq('saved-sheet hydration preserves half-typed amount and focus', await tab.page.evaluate(() => [
        document.getElementById('setup-amount').value, document.activeElement.id
      ]), ['125.', 'setup-amount']);
      check('saved-sheet research updates without losing exact model outcome', /STOPPED/.test(await tab.page.locator('#saved [data-model-update="matched"]').textContent()));
      if (shotsDir) {
        await tab.page.locator('#saved').screenshot({ path: path.join(shotsDir, 'reader-saved-hydrated.png') });
        await tab.page.locator('#saved [data-saved="signal"] .ss-chart-panel').screenshot({ path: path.join(shotsDir, 'reader-saved-original-chart.png') });
      }
      eq('saved-sheet hydration runtime errors', [...tab.errors], []);
    } finally { release(); await tab.context.close(); }
  }

  // Independent boundary controls each satisfy the checks that precede the
  // one they target: shape/metadata cases have correct declared bytes and SHA.
  const oldClose = full.data.observations.symbols.AAPL.c;
  const alteredRaw = Buffer.from(full.sidecarRaw.toString('utf8').replace('"c":' + oldClose, '"c":' + Number((oldClose + 0.01).toFixed(2))));
  check('digest negative control changes source bytes', !alteredRaw.equals(full.sidecarRaw));
  eq('digest negative control preserves byte length', alteredRaw.length, full.sidecarRaw.length);
  const malformed = JSON.parse(full.sidecarRaw); malformed.symbols.AAPL.c = 'invalid';
  const wrongMetadata = JSON.parse(full.sidecarRaw); wrongMetadata.days += 1;
  // A UTF-8 BOM changes three actual bytes. Only the declared length changes:
  // the old decoded-text hash incorrectly accepted the original sidecar SHA.
  const bom = Buffer.from([0xef, 0xbb, 0xbf]);
  const bomEnvelope = structuredClone(full.envelope);
  bomEnvelope.retained_observations.bytes += bom.length;
  const bomSidecar = bundle(JSON.stringify(bomEnvelope), Buffer.concat([bom, full.sidecarRaw]), full.canonicalRaw);
  const shortEnvelope = structuredClone(full.envelope);
  shortEnvelope.retained_observations.bytes += 1;
  const shortSidecar = bundle(JSON.stringify(shortEnvelope), full.sidecarRaw, full.canonicalRaw);
  const cases = [
    ['digest', full, alteredRaw, /digest/i],
    ['BOM byte identity', bomSidecar, null, /digest/i],
    ['length', full, Buffer.concat([full.sidecarRaw, Buffer.from('\n')]), /byte|length/i],
    ['short body', shortSidecar, null, /length/i],
    ['shape', changedSidecar(full, malformed), null, /invalid.*bar|invalid.*observation/i],
    ['metadata', changedSidecar(full, wrongMetadata), null, /metadata/i]
  ];
  for (const [name, record, badRaw, message] of cases) {
    const tab = await setup(record, { seed: savedSeed, sidecar: route => route.fulfill({ contentType: 'application/json', body: badRaw || record.sidecarRaw }) });
    try {
      const before = await tab.page.evaluate(() => JSON.stringify(localStorage));
      await tab.page.evaluate(() => SCStock.navigate('#/setups'));
      await tab.page.evaluate(() => SCStock.reader.ensure());
      eq(`${name}: malformed source remains unavailable`, (await readerState(tab.page)).state, 'unavailable');
      check(`${name}: its own transport check rejects the source`, message.test((await readerState(tab.page)).reason));
      eq(`${name}: failed hydration preserves local originals`, await tab.page.evaluate(() => JSON.stringify(localStorage)), before);
      eq(`${name}: invalid history is never installed`, await tab.page.evaluate(() => Object.keys(SCStock.data.observations.symbols).length), 0);
      check(`${name}: unavailable coverage stays explicit`, /unavailable|could not|retry/i.test(await tab.page.locator('#view-setups').textContent()));
    } finally { await tab.context.close(); }
  }

  // Boot and refresh share the same byte boundary. Fetch.text() used to strip
  // these bytes, then bind an unchanged morning SHA or report an unchanged file.
  for (const direct of [false, true]) {
    const record = { ...morning,
      readerRaw: Buffer.concat([bom, Buffer.from(morning.readerRaw)]),
      canonicalRaw: Buffer.concat([bom, canonical]) };
    const tab = await setup(record, { canonical: direct, receipt: direct ? await receipt('observed') : observed });
    try {
      eq(`${direct ? 'canonical' : 'projected'} BOM: unsupported JSON is refused before rendering`, await tab.page.getAttribute('html', 'data-ss-rendered'), 'error');
      eq(`${direct ? 'canonical' : 'projected'} BOM: normalized bytes cannot acquire a morning check`, tab.requests.filter(r => /\/morning\.json$/.test(r.url)).length, 0);
    } finally { await tab.context.close(); }
  }
  {
    const raw = Buffer.from(morning.readerRaw);
    // Invalid UTF-8 within a string remains parseable after Fetch.text()'s
    // replacement decoding, but cannot be an exact UTF-8 publication.
    const offset = raw.indexOf(Buffer.from(morning.envelope.data.cover.dek));
    check('invalid UTF-8 control targets the publication text', offset >= 0);
    raw[offset] = 0xff;
    const tab = await setup({ ...morning, readerRaw: raw });
    try {
      eq('invalid UTF-8 publication is refused before rendering', await tab.page.getAttribute('html', 'data-ss-rendered'), 'error');
    } finally { await tab.context.close(); }
  }
  {
    const tab = await setup(morning, { seed: privateSeed, receipt: observed });
    try {
      await waitMorning(tab.page);
      const before = await tab.page.evaluate(() => ({ data: JSON.stringify(SCStock.data), local: JSON.stringify(localStorage), hash: SCStock.observations.facts().recordHash }));
      eq('ordinary UTF-8 publication binds its actual served bytes', before.hash, sha(morning.readerRaw));
      tab.transport.current = { ...morning, readerRaw: Buffer.concat([bom, Buffer.from(morning.readerRaw)]) };
      await tab.page.evaluate(() => SCStock.checkUpdates());
      await tab.page.waitForFunction(() => document.getElementById('refresh-said').dataset.outcome !== 'checking');
      eq('BOM refresh cannot be called an unchanged publication', await tab.page.locator('#refresh-said').getAttribute('data-outcome'), 'failed');
      checkSame('refused BOM refresh preserves source identity and private inputs', await tab.page.evaluate(() => ({ data: JSON.stringify(SCStock.data), local: JSON.stringify(localStorage), hash: SCStock.observations.facts().recordHash })), before);
      const byteControl = await tab.page.evaluate(async ({ raw }) => {
        const { data, projection } = SCStock.reader.parse(raw, 'reader.json');
        const original = new TextEncoder().encode('\ufeff' + raw);
        const chunks = new ReadableStream({ start(controller) {
          controller.enqueue(original.slice(0, 1)); controller.enqueue(original.slice(1, 2));
          controller.enqueue(original.slice(2)); controller.close();
        } });
        const bytes = await SCStock.reader.read(new Response(chunks), original.length);
        SCStock.observations.reset(data, new Date('2026-09-11T13:35:00Z'));
        await SCStock.observations.bind(data, bytes, projection);
        return { bytesMatch: bytes.every((value, i) => value === original[i]) && bytes.length === original.length,
          leadingCode: SCStock.reader.decode(bytes).charCodeAt(0), ...SCStock.observations.facts() };
      }, { raw: morning.readerRaw });
      check('fragmented stream retains every original byte', byteControl.bytesMatch);
      eq('UTF-8 decoding preserves a BOM for JSON to reject', byteControl.leadingCode, 0xfeff);
      eq('byte-backed binding hashes the actual response, including BOM', byteControl.recordHash, sha(Buffer.concat([bom, Buffer.from(morning.readerRaw)])));
      eq('byte-backed binding cannot certify a normalized matching receipt', byteControl.state, 'unavailable');
      const bounds = await tab.page.evaluate(async () => {
        let cancelled = false, count = 0, oversized = false, header = false, headerCancelled = false, statusCancelled = false, oversizedNativeReads = 0;
        const chunks = new ReadableStream({ pull(controller) {
          if (count++ < 40) controller.enqueue(new Uint8Array(1024 * 1024)); else controller.close();
        }, cancel() { cancelled = true; } });
        const large = new Response(chunks), largeNative = large.arrayBuffer.bind(large);
        large.arrayBuffer = () => { oversizedNativeReads++; return largeNative(); };
        try { await SCStock.reader.read(large); } catch (error) { oversized = /byte limit/.test(error.message); }
        const advertised = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array([123, 125])); }, cancel() { headerCancelled = true; } });
        try { await SCStock.reader.read(new Response(advertised, { headers: { 'content-length': String(33 * 1024 * 1024) } })); }
        catch (error) { header = /size limit/.test(error.message); }
        const refused = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array([123, 125])); }, cancel() { statusCancelled = true; } });
        try { await SCStock.reader.read(new Response(refused, { status: 503 })); } catch (error) { /* expected HTTP refusal */ }
        let counterEOF = false, nativeReads = 0, prematureNativeRead = false;
        const small = new Response(new ReadableStream({
          start(controller) { controller.enqueue(new Uint8Array([123])); },
          pull(controller) { controller.enqueue(new Uint8Array([125])); controller.close(); }
        })), native = small.arrayBuffer.bind(small);
        const clone = small.clone.bind(small);
        small.clone = () => {
          const copy = clone(), acquire = copy.body.getReader.bind(copy.body);
          copy.body.getReader = () => {
            const reader = acquire(), read = reader.read.bind(reader);
            reader.read = async () => { const part = await read(); if (part.done) counterEOF = true; return part; };
            return reader;
          };
          return copy;
        };
        small.arrayBuffer = () => { nativeReads++; prematureNativeRead = !counterEOF; return native(); };
        const exact = await SCStock.reader.read(small, 2);
        return { oversized, cancelled, header, headerCancelled, statusCancelled, oversizedNativeReads, nativeReads, prematureNativeRead, exact: [...exact] };
      });
      eq('actual streamed size is bounded without trusting a header', bounds.oversized, true);
      eq('an oversized publication cancels its source stream', bounds.cancelled, true);
      eq('an oversized advertised publication is refused', bounds.header, true);
      eq('early header refusal cancels the unconsumed source', bounds.headerCancelled, true);
      eq('early HTTP refusal cancels the unconsumed source', bounds.statusCancelled, true);
      eq('oversize never enters native buffering', bounds.oversizedNativeReads, 0);
      eq('native buffering starts only after bounded EOF', [bounds.nativeReads, bounds.prematureNativeRead, bounds.exact], [1, false, [123, 125]]);
    } finally { await tab.context.close(); }
  }

  {
    let attempts = 0;
    const tab = await setup(next, { seed: savedSeed, now: PAGE_NOW, sidecar: route => {
      attempts++;
      return route.fulfill({ contentType: 'application/json', body: attempts === 1 ? Buffer.concat([next.sidecarRaw, Buffer.from('!')]) : next.sidecarRaw });
    } });
    try {
      await tab.page.evaluate(() => SCStock.navigate('#/setups')); await waitResearch(tab.page, 'unavailable');
      const retry = tab.page.locator('[data-research-load]').first();
      check('failed research has an explicit retry control', await retry.count() > 0);
      await retry.click(); await waitResearch(tab.page, 'complete');
      eq('retry makes one new public request', attempts, 2);
      checkSame('successful retry hydrates exact canonical observations', await tab.page.evaluate(() => SCStock.data.observations), next.data.observations);
      const parseRefusals = await tab.page.evaluate(raw => {
        const original = JSON.parse(raw), results = [];
        for (const path of ['../data.json', 'https://example.com/file.json', original.retained_observations.path + '?ticker=ZZPRIVATE']) {
          const value = structuredClone(original); value.retained_observations.path = path;
          try { SCStock.reader.parse(JSON.stringify(value), new URL('reader.json', location.href).href); results.push(false); } catch { results.push(true); }
        }
        return results;
      }, next.readerRaw);
      eq('invalid traversal, foreign and symbol-bearing paths are refused before request', parseRefusals, [true, true, true]);
    } finally { await tab.context.close(); }
  }

  {
    let release, oldStarted;
    const oldGate = new Promise(resolve => { release = resolve; });
    const started = new Promise(resolve => { oldStarted = resolve; });
    const tab = await setup(next, { seed: savedSeed, now: PAGE_NOW, sidecar: async route => {
      if (new URL(route.request().url()).pathname === next.sidecarPath) {
        oldStarted(); await oldGate;
        await route.fulfill({ contentType: 'application/json', body: next.sidecarRaw }).catch(() => {});
      } else await route.fulfill({ contentType: 'application/json', body: revised.sidecarRaw });
    } });
    try {
      await tab.page.evaluate(() => SCStock.navigate('#/setups')); await started;
      tab.transport.current = revised;
      await tab.page.evaluate(() => SCStock.checkUpdates());
      await tab.page.waitForFunction(digest => SCStock.reader.status().sidecarSha === digest && SCStock.reader.status().state === 'complete', revised.envelope.retained_observations.sha256);
      release(); await tab.page.waitForTimeout(80);
      eq('late previous-publication hydration cannot overwrite a same-session revision', await tab.page.evaluate(() => SCStock.data.observations.symbols.AAPL.c), revised.data.observations.symbols.AAPL.c);
      eq('the revision remains the attached sidecar identity', (await readerState(tab.page)).sidecarSha, revised.envelope.retained_observations.sha256);
      tab.transport.current = full;
      await tab.page.evaluate(() => SCStock.checkUpdates());
      await tab.page.waitForTimeout(100);
      eq('older publication refusal keeps the newer sidecar', (await readerState(tab.page)).sidecarSha, revised.envelope.retained_observations.sha256);
    } finally { release(); await tab.context.close(); }
  }

  {
    const tab = await setup(morning, { receipt: observed });
    try {
      await waitMorning(tab.page);
      eq('reader-bound morning receipt accepted against actual reader bytes', await tab.page.evaluate(() => SCStock.observations.facts().state), 'loaded');
      await tab.page.locator('#morning-open').click();
      await tab.page.locator('.ss-morning__prep > summary').click();
      await tab.page.locator('#morning-cash').fill('125.'); await tab.page.locator('#morning-cash').focus();
      const before = await tab.page.evaluate(() => { window.__readerChart = document.querySelector('#detail svg, #detail canvas'); return SCStock.observations.facts(); });
      await tab.page.evaluate(() => SCStock.reader.ensure()); await waitResearch(tab.page, 'complete');
      eq('sidecar hydration does not reset exact morning receipt', await tab.page.evaluate(() => SCStock.observations.facts().state), before.state);
      eq('sidecar hydration preserves morning draft and focus', await tab.page.evaluate(() => [document.getElementById('morning-cash').value, document.activeElement.id]), ['125.', 'morning-cash']);
      eq('sidecar hydration preserves the existing chart node', await tab.page.evaluate(() => !!window.__readerChart && window.__readerChart === document.querySelector('#detail svg, #detail canvas')), true);
      tab.transport.receipt = await receipt('observed');
      await tab.page.evaluate(() => SCStock.observations.reload()); await waitMorning(tab.page);
      eq('legacy canonical-only receipt cannot certify projected quote bytes', await tab.page.evaluate(() => SCStock.observations.facts().state), 'unavailable');
    } finally { await tab.context.close(); }
  }

  // A copied canonical SHA is insufficient when the served reader bytes differ.
  {
    const envelope = structuredClone(morning.envelope);
    envelope.data.cover.dek += ' Explicit malformed transport control.';
    const tampered = bundle(JSON.stringify(envelope), morning.sidecarRaw, canonical);
    const tab = await setup(tampered, { receipt: observed });
    try {
      await waitMorning(tab.page);
      eq('copied canonical SHA does not hide reader-byte tampering', await tab.page.evaluate(() => SCStock.observations.facts().state), 'unavailable');
    } finally { await tab.context.close(); }
  }

  {
    const tab = await setup(morning, { receipt: await receipt('halted') });
    try {
      await waitMorning(tab.page);
      eq('fresh projected tab refuses legacy quote certification', await tab.page.evaluate(() => SCStock.observations.facts().state), 'unavailable');
      check('fresh projected tab retains independently sourced legacy halt', (await tab.page.evaluate(() => SCStock.observations.facts().restricted)).length > 0);
      eq('fresh projected tab with legacy halt withholds copying', await tab.page.locator('#detail [data-copy]').count(), 0);
    } finally { await tab.context.close(); }
  }

  {
    const legacyHalt = await receipt('halted');
    const tab = await setup(morning, { canonical: true, receipt: legacyHalt });
    try {
      await waitMorning(tab.page);
      eq('legacy canonical receipt remains usable under exact canonical bytes', await tab.page.evaluate(() => SCStock.observations.facts().state), 'loaded');
      eq('legacy source-backed halt initially withholds copying', await tab.page.locator('#detail [data-copy]').count(), 0);
      // Upgrade the same canonical source through its real reader-bound outage
      // receipt. Positive facts must survive even though quote coverage fails.
      tab.transport.current = morning;
      tab.transport.receipt = await receipt('reader-halt-outage');
      await tab.page.evaluate(() => { SCStock.dataUrl = 'reader.json'; SCStock.checkUpdates(); });
      await tab.page.waitForFunction(() => SCStock.reader.status().projected);
      await waitMorning(tab.page);
      eq('legacy positive halt survives reader rollout and provider outage', await tab.page.locator('#detail [data-copy]').count(), 0);
      tab.transport.receipt = await receipt('reader-halt-recovered');
      await tab.page.evaluate(() => { SCStock.observations.clock(new Date('2026-09-11T13:35:45Z')); SCStock.observations.reload(); });
      await waitMorning(tab.page);
      check('newer source-backed resumption restores only the original conditional control', await tab.page.locator('#detail [data-copy]').count() > 0);
    } finally { await tab.context.close(); }
  }
}
