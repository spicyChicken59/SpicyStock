/* Browser source inspection over producer-written, explicitly offline records.
   Boundary cases alter only served transport copies, never fixture bytes. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..'), DIR = 'tests/fixtures/issuer-evidence';
const NOW = '2026-10-10T06:20:00Z', PRIVATE = 'ZZPRIVATE-issuer-234.56';
const sha = raw => createHash('sha256').update(raw).digest('hex');

export async function checkIssuerEvidence({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- issuer sources: exact publication, bounded public transport, inert excerpts and incomplete coverage');
  const file = name => readFile(path.join(ROOT, DIR, name));
  const publicationRaw = await file('publication.json'), readerRaw = await file('reader.json');
  const variants = {};
  for (const name of ['collected', 'metadata-only', 'identity-unverified', 'outage', 'inapplicable']) {
    variants[name] = { receipt: JSON.parse(await file(name + '-receipt.json')), raw: await file(name + '-bundle.json') };
  }
  const original = variants.collected, originalBundle = JSON.parse(original.raw);
  const bodyText = page => page.locator('[data-issuer-body]').innerText();
  const wait = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.issuerEvidence.status().state));
  const status = page => page.evaluate(() => SCStock.issuerEvidence.status());
  const publicRequests = requests => requests.filter(x => /\/issuer-evidence(?:\.json|\/)/.test(x.url));
  function changed(editReceipt, editBundle) {
    const receipt = structuredClone(original.receipt), bundle = structuredClone(originalBundle);
    let raw = original.raw;
    if (editBundle) { editBundle(bundle); raw = Buffer.from(JSON.stringify(bundle)); receipt.bundle = { sha256: sha(raw), bytes: raw.length, path: 'issuer-evidence/' + sha(raw) + '.json' }; }
    if (editReceipt) editReceipt(receipt);
    // Publication controls are internally coherent transports: only comparison
    // with the actual browser publication may reject them, not a second guard.
    if (!editBundle && JSON.stringify(receipt.publication) !== JSON.stringify(original.receipt.publication)) {
      bundle.publication = structuredClone(receipt.publication); raw = Buffer.from(JSON.stringify(bundle));
      receipt.bundle = { sha256: sha(raw), bytes: raw.length, path: 'issuer-evidence/' + sha(raw) + '.json' };
    }
    return { receipt, raw };
  }
  async function setup(options = {}) {
    const requests = [], transport = { current: options.variant || original, held: null, release: null };
    const tab = await open(browser, base, options.canonical ? '/issuer-canonical-control.json' : null, NOW, options.width || 1280, {
      theme: options.theme || 'dark', reducedMotion: 'reduce', hash: '#/explore/bursts/AAPL', lens: 'all',
      beforeLoad: async (page, context) => {
        await context.addCookies([{ name: 'issuer_private_cookie', value: PRIVATE, url: base }]);
        page.on('request', request => requests.push({ url: request.url(), body: request.postData(), headers: request.headers(), method: request.method() }));
        await page.addInitScript(seed => {
          localStorage.setItem('issuer-test-private-sentinel', seed);
          window.__issuerFetches = [];
          const original = window.fetch;
          window.fetch = function(url, opts = {}) {
            if (/\/issuer-evidence(?:\.json|\/)/.test(String(url))) window.__issuerFetches.push({ url: String(url), credentials: opts.credentials, referrerPolicy: opts.referrerPolicy, mode: opts.mode, redirect: opts.redirect, body: opts.body || null, method: opts.method || 'GET' });
            return original.apply(this, arguments);
          };
        }, PRIVATE);
        await page.route('**/docs/reader.json', route => route.fulfill({ contentType: 'application/json', body: readerRaw }));
        await page.route('**/issuer-canonical-control.json', route => route.fulfill({ contentType: 'application/json', body: publicationRaw }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: '{}' }));
        await page.route('**/issuer-evidence.json', async route => {
          const value = transport.current;
          if (transport.held === 'receipt') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ contentType: 'application/json', body: typeof value.receipt === 'string' ? value.receipt : JSON.stringify(value.receipt) });
        });
        await page.route('**/issuer-evidence/*.json', async route => {
          const value = transport.current;
          if (transport.held === 'bundle') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ contentType: 'application/json', body: value.raw });
        });
        if (options.beforeLoad) await options.beforeLoad(page, context);
      }
    });
    await tab.page.waitForFunction(() => !!SCStock.observations.facts().recordHash);
    await tab.page.waitForFunction(() => ['loaded', 'unavailable', 'practice'].includes(SCStock.observations.facts().state));
    await tab.page.locator('#morning-open').click();
    return { ...tab, transport, requests };
  }
  const reveal = async page => {
    await page.locator('[data-issuer-evidence] > summary').click(); await wait(page);
  };
  for (const [width, theme, canonical] of [[1280, 'dark', false], [390, 'light', false], [390, 'dark', true], [1280, 'light', true]]) {
    const { page, context, errors, requests } = await setup({ width, theme, canonical });
    try {
      eq(`${width}/${theme}: closed disclosure makes no source request`, publicRequests(requests).length, 0);
      if (!canonical) eq('source reader causes no eager canonical/history/research download', requests.filter(x => /\/(?:data\.json|reader-observations\/|history\/|historical-findings\.json)/.test(new URL(x.url).pathname)).length, 0);
      eq('exact browser publication hash settled before source tests', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(canonical ? publicationRaw : readerRaw));
      const before = await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), model: JSON.stringify(SCStock.model), storage: JSON.stringify(localStorage), morning: SCStock.observations.facts(), copies: [...document.querySelectorAll('[data-copy]')].map(n => n.getAttribute('data-copy')) }));
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('234.56');
      await page.locator('#morning-cash').focus();
      await page.evaluate(() => { window.__issuerCashNode = document.getElementById('morning-cash'); window.__issuerChartNode = document.querySelector('#detail svg, #detail canvas'); document.querySelector('[data-issuer-evidence]').open = true; });
      await wait(page);
      eq('producer receipt and bundle are readable', (await status(page)).state, 'loaded');
      eq('source completion preserves private input focus', await page.evaluate(() => document.activeElement === window.__issuerCashNode), true);
      eq('source completion preserves a real existing chart node', await page.evaluate(() => !!window.__issuerChartNode && document.querySelector('#detail svg, #detail canvas') === window.__issuerChartNode), true);
      check('verified issuer plus CIK are named', (await bodyText(page)).includes('Synthetic AAPL issuer fixture') && (await bodyText(page)).includes('0000320193'));
      check('selection distinguishes published ticket and excluded research', await page.locator('[data-issuer-choice]').evaluate(n => [...n.options].some(x => /AAPL.*published ticket/.test(x.textContent)) && [...n.options].some(x => /ZIM.*excluded research/.test(x.textContent))));
      check('coverage states selected, missing and unreviewed remainder', /1 eligible reports not selected/.test(await bodyText(page)) && /unreviewed/.test(await bodyText(page)) && /not a year of reviewed content/.test(await bodyText(page)));
      const docs = page.locator('[data-issuer-document]');
      await docs.first().locator('summary').click();
      check('acceptance, filing, report, release and retrieval are separated', /SEC acceptance:/.test(await bodyText(page)) && /issuer release date not extracted/.test(await bodyText(page)) && /Retrieved \/ checked:/.test(await bodyText(page)));
      check('HTML-like excerpt is inert literal text', (await page.locator('[data-issuer-excerpt]').first().textContent()).includes('<img src=x onerror=alert(1)>') && await page.locator('[data-issuer-body] img, [data-issuer-body] script').count() === 0);
      check('stripped script body is absent', !(await bodyText(page)).includes('issuer-script-must-not-run'));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await docs.first().locator('summary').scrollIntoViewIfNeeded();
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `issuer-excerpt-${width}-${theme}.png`) });
      }
      eq('source inspection preserves cash DOM and draft', await page.evaluate(() => [document.getElementById('morning-cash') === window.__issuerCashNode, document.getElementById('morning-cash').value]), [true, '234.56']);
      eq('source inspection never changes data, model, local saves, morning receipt or copies', await page.evaluate(() => ({ data: JSON.stringify(SCStock.data), model: JSON.stringify(SCStock.model), storage: JSON.stringify(localStorage), morning: SCStock.observations.facts(), copies: [...document.querySelectorAll('[data-copy]')].map(n => n.getAttribute('data-copy')) })), before);
      eq('one fixed receipt and one digest bundle requested', publicRequests(requests).map(x => new URL(x.url).pathname), ['/docs/issuer-evidence.json', '/docs/' + original.receipt.bundle.path]);
      check('source requests omit cookies, referrer, body and private inputs', publicRequests(requests).every(x => x.method === 'GET' && !x.body && !x.headers.cookie && !x.headers.referer && !x.url.includes(PRIVATE) && !x.url.includes('234.56')));
      check('browser transport explicitly refuses redirects and cross-origin credentials', (await page.evaluate(() => window.__issuerFetches)).every(x => x.credentials === 'omit' && x.referrerPolicy === 'no-referrer' && x.mode === 'same-origin' && x.redirect === 'error' && x.body === null));
      await page.locator('[data-issuer-choice]').selectOption('anticipation:ZIM');
      check('excluded research shows archived unresolved cash acquisition', /excluded research — no entry ticket/.test(await bodyText(page)) && /35/.test(await page.locator('[data-issuer-anchors]').innerText()));
      check('newer actual guidance/regulatory documents cannot erase anchor', (await bodyText(page)).includes('Known event evidence') && /do not|does not|never/.test(await page.locator('[data-issuer-evidence]').innerText()));
      eq('selector uses shared bundle without a symbol request', publicRequests(requests).length, 2);
      check(`${width}/${theme}: source body fits phone/dialog`, await page.locator('#morning-desk').evaluate(n => n.scrollWidth <= n.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('[data-issuer-evidence] > summary').scrollIntoViewIfNeeded();
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `issuer-${width}-${theme}.png`) });
      }
      eq('issuer source browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  const tab = await setup();
  try {
    const { page, transport } = tab;
    await reveal(page);
    for (const variant of ['metadata-only', 'identity-unverified', 'outage']) {
      transport.current = variants[variant]; await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
      eq(variant + ' is an honestly readable incomplete producer result', (await status(page)).state, 'loaded');
      await page.locator('[data-issuer-choice]').selectOption('burst:AAPL');
      eq(variant + ' has no invented issuer excerpts', await page.locator('[data-issuer-document]').count(), 0);
      check(variant + ' explains unreviewed or unverified coverage', /unreviewed|Unverified|No document excerpts/.test(await bodyText(page)));
      await page.locator('[data-issuer-choice]').selectOption('anticipation:ZIM');
      check(variant + ' retains known exclusion independently', /35/.test(await page.locator('[data-issuer-anchors]').innerText()));
    }
    transport.current = variants.inapplicable; await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
    eq('actual skipped collection remains readable source context', (await status(page)).state, 'loaded');
    check('wrong scan session is named without a false fetch-cap claim', /scan session was not current/.test(await bodyText(page)) && /No SEC collection ran/.test(await bodyText(page)) && !/collection cap|exceeded the fetch cap/.test(await bodyText(page)));
    check('skipped collection still retains the archived exclusion', /35/.test(await page.locator('[data-issuer-anchors]').innerText()));
    transport.current = changed(null, b => {
      const excerpt = b.issuers[0].documents[0].excerpt;
      excerpt.text = 'W'.repeat(256); excerpt.characters = excerpt.normalized_characters = 256;
      excerpt.truncated = false; excerpt.sha256 = sha(excerpt.text);
    });
    await page.setViewportSize({ width: 390, height: 900 });
    await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
    await page.locator('[data-issuer-choice]').selectOption('burst:AAPL');
    await page.locator('[data-issuer-document]').first().locator('summary').click();
    eq('long unbroken source excerpt remains readable', (await status(page)).state, 'loaded');
    check('bounded unbroken source text cannot widen the phone dialog', await page.locator('#morning-desk').evaluate(n => n.scrollWidth <= n.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
    await page.locator('[data-issuer-choice]').selectOption('anticipation:ZIM');
    const boundary = [
      ['canonical publication hash', r => { r.publication.data_sha256 = '0'.repeat(64); }],
      ['actual reader hash', r => { r.publication.reader_sha256 = r.publication.data_sha256; }],
      ['context identity', r => { r.publication.context_sha256 = '0'.repeat(64); }],
      ['source run identity', r => { r.publication.run_id += '-wrong'; }],
      ['publication time', r => { r.publication.published_at = '2026-09-10T22:31:00Z'; }],
      ['applicable session', r => { r.publication.applicable_session = '2026-09-14'; }],
      ['rules identity', r => { r.publication.rules_version = 'wrong'; }],
      ['rehearsal', r => { r.dry_run = true; }],
      ['future collection', r => { r.generated_at = '2026-10-11T06:20:00Z'; r.expires_at = '2026-10-12T06:20:00Z'; }],
      ['source limits', r => { r.policy.max_issuers = 999; }],
      ['path traversal', r => { r.bundle.path = '../private.json'; }],
      ['external path', r => { r.bundle.path = 'https://example.com/secret.json'; }],
      ['oversized declared bundle', r => { r.bundle.bytes = 2097153; }],
      ['wrong declared bundle length', r => { r.bundle.bytes -= 1; }],
      ['raw bundle digest', r => { r.bundle.sha256 = '0'.repeat(64); r.bundle.path = 'issuer-evidence/' + r.bundle.sha256 + '.json'; }],
      ['bundle publication mismatch', null, b => { b.publication.run_id += '-wrong'; }],
      ['candidate membership', null, b => { b.candidates.pop(); }],
      ['candidate plan', null, b => { b.candidates[0].plan_sha256 = '0'.repeat(64); }],
      ['candidate evidence', null, b => { b.candidates[0].evidence_id = '0'.repeat(64); }],
      ['candidate stage', null, b => { b.candidates[0].kind = 'anticipation'; }],
      ['candidate admission', null, b => { b.candidates[0].admission = 'known_event_excluded'; }],
      ['archived anchor removal', null, b => { b.candidates.find(c => c.ticker === 'ZIM').anchors = []; }],
      ['verified CIK path', null, b => { b.issuers[0].identity.cik += 1; }],
      ['document accession path', null, b => { b.issuers[0].documents[0].source.url = b.issuers[0].documents[0].source.url.replace('/320193/', '/1045810/'); }],
      ['unsafe source URL', null, b => { b.issuers[0].documents[0].source.url = 'javascript:alert(1)'; }],
      ['excerpt digest', null, b => { b.issuers[0].documents[0].excerpt.sha256 = '0'.repeat(64); }],
      ['future source check', null, b => { b.issuers[0].documents[0].source.checked_at = '2026-10-11T06:20:00Z'; }],
      ['impossible source date', null, b => { b.issuers[0].documents[0].source.fetched_at = '2026-09-31T06:20:00Z'; }],
      ['cache claims fresh SEC check', null, b => { b.issuers[0].documents[0].source.cache_status = 'verified_cache'; b.issuers[0].documents[0].source.fetched_at = '2026-10-10T05:20:00Z'; }],
      ['expired cached document', null, b => { const s = b.issuers[0].documents[0].source; s.cache_status = 'verified_cache'; s.fetched_at = s.checked_at = '2026-10-08T06:20:00Z'; }],
      ['cached submissions forbidden', null, b => { b.issuers[0].identity.submissions_source.cache_status = 'verified_cache'; }],
      ['metadata remainder arithmetic', null, b => { b.issuers[0].index.not_selected_count += 1; }],
      ['exhibit remainder arithmetic', null, b => { b.issuers[0].index.exhibit_links_observed += 1; }]
    ];
    for (const [name, editReceipt, editBundle] of boundary) {
      transport.current = changed(editReceipt, editBundle);
      await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
      eq(name + ' is refused independently', (await status(page)).state, 'unavailable');
      eq(name + ' leaves no fetched excerpts', await page.locator('[data-issuer-document]').count(), 0);
      check(name + ' cannot erase current archived event evidence', /35/.test(await page.locator('[data-issuer-anchors]').innerText()));
    }
    transport.current = { receipt: ' '.repeat(65537), raw: original.raw };
    await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
    check('oversized receipt refused before decoding', /size limit|declared size/.test((await status(page)).issue));
    const bom = changed(r => { r.bundle.bytes += 3; });
    bom.raw = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), original.raw]);
    transport.current = bom; await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
    eq('raw UTF-8 BOM cannot bypass exact byte digest', (await status(page)).state, 'unavailable');
    check('raw BOM fails the raw digest boundary', /digest differs/.test((await status(page)).issue));
    transport.current = original; await page.evaluate(() => SCStock.issuerEvidence.reload()); await wait(page);
    eq('valid retry recovers after every malformed boundary', (await status(page)).state, 'loaded');
    await page.evaluate(() => { SCStock.now = '2026-10-12T06:20:00Z'; SCStock.issuerEvidence.update(SCStock.data); });
    check('expired receipt is dated research, never clearance', /aged receipt/.test(await page.locator('[data-issuer-status]').innerText()));
    check('receipt aging never clears excluded anchor', /35/.test(await page.locator('[data-issuer-anchors]').innerText()));
    await page.evaluate(() => { SCStock.now = '2026-10-09T06:20:00Z'; window.dispatchEvent(new Event('focus')); });
    check('clock rollback withdraws freshness claim without inventing clearance', /browser clock cannot verify/.test(await page.locator('[data-issuer-status]').innerText()));
  } finally { await tab.context.close(); }

  // A held old response must not attach its source body after a new publication.
  const race = await setup();
  try {
    race.transport.held = 'bundle';
    await race.page.locator('[data-issuer-evidence] > summary').click();
    for (let n = 0; n < 100 && !race.transport.release; n++) await race.page.waitForTimeout(20);
    check('race control actually holds a requested old bundle', !!race.transport.release);
    const nextRaw = await readFile(path.join(ROOT, 'tests/fixtures/morning/full-publication.json'), 'utf8');
    await race.page.evaluate(async raw => {
      const next = JSON.parse(raw); SCStock.render(next, new Date('2026-10-10T06:20:00Z'));
      await SCStock.observations.bind(next, raw);
    }, nextRaw);
    const release = race.transport.release; race.transport.held = null;
    if (release) release();
    await wait(race.page);
    eq('old source bundle cannot bind to the replacement publication', (await status(race.page)).state, 'unavailable');
    eq('old issuer content absent after replacement', await race.page.locator('[data-issuer-document]').count(), 0);
    check('new publication exact hash remains authoritative', await race.page.evaluate(want => SCStock.observations.facts().canonicalHash === want, sha(nextRaw)));
  } finally { if (race.transport.release) race.transport.release(); await race.context.close(); }

  const noCrypto = await setup();
  try {
    await noCrypto.page.evaluate(() => Object.defineProperty(window, 'crypto', { configurable: true, value: undefined }));
    await reveal(noCrypto.page);
    eq('missing crypto refuses source inspection', (await status(noCrypto.page)).state, 'unavailable');
    eq('missing crypto makes no unverified source request', publicRequests(noCrypto.requests).length, 0);
    await noCrypto.page.locator('[data-issuer-choice]').selectOption('anticipation:ZIM');
    check('missing crypto cannot erase archived source facts', /35/.test(await noCrypto.page.locator('[data-issuer-anchors]').innerText()));
  } finally { await noCrypto.context.close(); }

  const noModule = await setup({ beforeLoad: page => page.route('**/app-issuer-evidence.js', route => route.fulfill({ contentType: 'application/javascript', body: '/* optional source reader unavailable */' })) });
  try {
    check('missing optional source module keeps the ordinary page readable', await noModule.page.locator('html').getAttribute('data-ss-rendered') !== 'error');
    check('missing module is explained without clearance', /unavailable.*independently/.test(await noModule.page.locator('[data-issuer-unavailable]').innerText()));
    await noModule.page.locator('.ss-morning__prep > summary').click();
    await noModule.page.locator('#morning-cash').fill('234.56');
    eq('missing source module leaves ordinary cash input usable', await noModule.page.locator('#morning-cash').inputValue(), '234.56');
    eq('missing source module has no uncaught application errors', [...noModule.errors], []);
  } finally { await noModule.context.close(); }
}
