/* Backend-generated observations, bound to the producer's exact publication
   bytes. Malformed responses below are explicit browser boundary controls. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const FIXTURES = path.join(ROOT, 'tests/fixtures/morning');
const NOW = '2026-09-11T13:35:00Z';

export async function checkObservations({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- morning observations: exact publication, expiry and narrow-only event refusals');
  const raw = await readFile(path.join(FIXTURES, 'full-publication.json'), 'utf8');
  const publication = JSON.parse(raw), digest = createHash('sha256').update(raw).digest('hex');
  const records = Object.fromEntries(await Promise.all(['observed', 'outage', 'no-tickets', 'halted', 'resumed', 'corporate-excluded', 'corporate-retained', 'corporate-resolved', 'corporate-resolution-carried', 'qeta-captured'].map(async name => [name, JSON.parse(await readFile(path.join(FIXTURES, name + '.json'), 'utf8'))])));
  const wait = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.observations.facts().state));
  const facts = page => page.evaluate(() => SCStock.observations.facts());
  const setup = async (name = 'observed', options = {}) => {
    const response = { body: JSON.stringify(records[name]), status: 200, delay: 0 };
    const requests = [];
    const tab = await open(browser, base, '/tests/fixtures/morning/' + (name === 'no-tickets' ? 'red' : 'full') + '-publication.json', options.now || NOW, options.width || 1280, {
      hash: '#/explore/bursts/AAPL', theme: options.theme || 'dark', reducedMotion: 'reduce',
      beforeLoad: async page => {
        await page.addInitScript(() => {
          window.__observationFetches = []; window.__copies = [];
          const fetch = window.fetch;
          window.fetch = function(url, options) { if (String(url).endsWith('/morning.json')) window.__observationFetches.push({ url: String(url), credentials: options.credentials, mode: options.mode, cache: options.cache }); return fetch.apply(this, arguments); };
          Object.defineProperty(navigator, 'clipboard', { value: { writeText: async value => window.__copies.push(value) }, configurable: true });
        });
        await page.route('**/morning.json', async route => {
          requests.push(route.request().url());
          const reply = { ...response };
          if (reply.delay) await new Promise(resolve => setTimeout(resolve, reply.delay));
          await route.fulfill({ status: reply.status, contentType: 'application/json', body: reply.body }).catch(() => {});
        });
        if (options.beforeLoad) await options.beforeLoad(page);
      }
    });
    await wait(tab.page);
    return { ...tab, response, requests, async reload(value, status = 200) {
      response.body = typeof value === 'string' ? value : JSON.stringify(value); response.status = status;
      await tab.page.evaluate(() => SCStock.observations.reload()); await wait(tab.page);
    } };
  };

  for (const width of [1280, 390]) for (const theme of ['dark', 'light']) {
    const tab = await setup('observed', { width, theme }); const { page, context, errors } = tab;
    try {
      eq(`${width}/${theme}: exact publication SHA matched`, (await facts(page)).recordHash, digest);
      eq(`${width}/${theme}: generated observation accepted`, (await facts(page)).state, 'loaded');
      eq('static observations never rewrite publication', await page.evaluate(() => JSON.stringify(SCStock.data)), JSON.stringify(publication));
      eq('same-origin read sends no private symbols or credentials', await page.evaluate(() => __observationFetches), [{ url: base + '/docs/morning.json', credentials: 'omit', mode: 'same-origin', cache: 'no-store' }]);
      const offered = await page.locator('#detail [data-copy]').count();
      check('within-band observation preserves conditional order controls', offered > 0);
      await page.locator('#disc-observations > summary').click();
      const detail = await page.locator('#disc-observations').textContent();
      check('IEX bid, ask and spread are timestamped', detail.includes('$125') && detail.includes('$125.02') && detail.includes('8:35:00 AM CT') && detail.includes('single venue'));
      check('entitlement describes actual request and feed limits', detail.includes('request succeeded') && detail.includes('at least 15 minutes') && detail.includes('data-through time is unavailable'));
      check('unmatched halt coverage never implies clearance', detail.includes('not listed') && detail.includes('absence is not trading clearance') && detail.includes('not comprehensive event clearance'));
      check('recorded price comparison never promises an entry', detail.includes('within published band') && detail.includes('not an entry or cancellation instruction'));
      await page.locator('#morning-open').click();
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('950');
      await page.locator('#morning-cash').focus();
      await page.evaluate(() => SCStock.observations.clock(new Date('2026-09-11T13:36:01Z')));
      check('quote expiry appears while the entry window remains open', (await page.locator('[data-observations="summary"] h3').textContent()).includes('stale'));
      eq('expiry preserves cash value and focus', await page.evaluate(() => [document.getElementById('morning-cash').value, document.activeElement.id]), ['950', 'morning-cash']);
      eq('quote expiry cannot create or remove a conditional strategy ticket', await page.locator('#detail [data-copy]').count(), offered);
      check('reload wording names the static-file limit', (await page.locator('[data-observations="summary"]').textContent()).includes('does not request a new market quote'));
      check(`${width}/${theme}: observation desk fits`, await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `observations-${width}-${theme}.png`) });
      }
      await page.locator('#morning-close').click();
      await page.evaluate(() => SCStock.observations.clock(new Date('2026-09-11T13:40:01Z')));
      eq('receipt expires independently of quote age', (await facts(page)).fresh, false);
      eq('browser observation errors', errors, []);
    } finally { await context.close(); }
  }

  for (const name of ['outage', 'no-tickets']) {
    const tab = await setup(name);
    try {
      eq(name + ': correctly bound outcome is readable', (await facts(tab.page)).state, 'loaded');
      check(name + ': provider failure or no-ticket reason is explicit', (await facts(tab.page)).headline.includes(name === 'outage' ? 'incomplete' : 'No admitted tickets'));
      if (name === 'no-tickets') eq('no-ticket snapshot cannot invent copying', await tab.page.locator('#detail [data-copy]').count(), 0);
      eq(name + ': no browser errors', tab.errors, []);
    } finally { await tab.context.close(); }
  }

  const tab = await setup();
  try {
    const { page } = tab;
    await page.evaluate(() => { window.__oldCopy = document.querySelector('#detail .ss-action [data-copy]'); });
    await tab.reload(records.halted);
    eq('known halt narrows the action area', await page.locator('#detail .ss-action').getAttribute('data-ticket'), 'blocked');
    eq('known halt removes all selected entry-copy controls', await page.locator('#detail [data-copy]').count(), 0);
    eq('known halt removes the executable sheet row', await page.locator('#order-sheet tbody tr[data-ticker="AAPL"]').count(), 0);
    check('archived order remains available for inspection', await page.locator('#detail [data-recorded-ticket="AAPL"]').count() === 1);
    await page.evaluate(() => window.__oldCopy.click());
    eq('old detached copy control still checks current halt at click time', await page.evaluate(() => __copies.length), 0);
    await page.evaluate(() => SCStock.observations.clock(new Date('2026-09-11T13:41:00Z')));
    await tab.reload(records.outage);
    eq('expiry and provider outage cannot revive entry copying', await page.locator('#detail [data-copy]').count(), 0);
    tab.response.status = 404;
    await page.reload(); await wait(page);
    eq('tab reload and 404 retain source-backed halt from bounded cache', await page.locator('#detail [data-copy]').count(), 0);
    check('cached evidence is explicitly not a new quote check', (await page.locator('#disc-observations').textContent()).includes('Cached evidence is not a new quote check'));
    const malformed = structuredClone(records.resumed);
    malformed.rows[0].events.halt.events = [{}];
    await tab.reload(malformed);
    eq('malformed resumption cannot clear a remembered halt', await page.locator('#detail [data-copy]').count(), 0);
    await page.evaluate(at => SCStock.observations.clock(new Date(at)), records.resumed.generated_at);
    const rollback = structuredClone(records.resumed);
    Object.assign(rollback.coverage.halts, { source_published_at: '2026-09-11T13:34:45Z', source_age_seconds: 45, expires_at: '2026-09-11T13:37:45Z' });
    await tab.reload(rollback);
    eq('older halt source cannot clear a newer remembered restriction', await page.locator('#detail [data-copy]').count(), 0);
    await tab.reload(records.resumed);
    check('only newer source-backed resumption releases the extra halt restriction', await page.locator('#detail [data-copy]').count() > 0);
    eq('resumption does not rewrite published model admission', await page.evaluate(() => SCStock.model.byId['bursts:AAPL'].status), 'ticket');
    eq('halt browser errors', tab.errors, []);
  } finally { await tab.context.close(); }

  const corporate = await setup('corporate-excluded', { now: '2026-09-11T13:36:00Z' });
  try {
    eq('new source-backed corporate exclusion narrows an older admitted order', await corporate.page.locator('#detail [data-copy]').count(), 0);
    check('corporate source is visible', await corporate.page.locator('#disc-observations a[href="https://example.invalid/synthetic-event"]').count() > 0);
    await corporate.reload(records.observed);
    eq('registry omission cannot remove a known corporate exclusion', await corporate.page.locator('#detail [data-copy]').count(), 0);
    await corporate.page.evaluate(at => SCStock.observations.clock(new Date(at)), records['corporate-retained'].generated_at);
    await corporate.reload(records['corporate-retained']);
    eq('explicit retained corporate evidence is readable', (await facts(corporate.page)).state, 'loaded');
    corporate.response.status = 404;
    await corporate.page.reload(); await wait(corporate.page);
    eq('reload/outage preserve known corporate exclusion', await corporate.page.locator('#detail [data-copy]').count(), 0);
    const invalid = structuredClone(records['corporate-resolution-carried']);
    invalid.corporate_resolutions[0].event_id = 'unrelated-event';
    await corporate.reload(invalid);
    eq('unrelated corporate proof cannot release a remembered event', await corporate.page.locator('#detail [data-copy]').count(), 0);
    await corporate.reload(records['corporate-resolution-carried']);
    check('carried explicit source-backed corporate resolution releases only the extra refusal', await corporate.page.locator('#detail [data-copy]').count() > 0);
    eq('corporate resolution preserves original plan admission', await corporate.page.evaluate(() => SCStock.model.byId['bursts:AAPL'].status), 'ticket');
  } finally { await corporate.context.close(); }

  for (const kind of ['halted', 'corporate-excluded']) for (const freshTab of [false, true]) {
    const revised = raw + '\n';
    const tab = await setup(kind, { beforeLoad: freshTab ? page => page.route('**/tests/fixtures/morning/full-publication.json', route => route.fulfill({ contentType: 'application/json', body: revised })) : undefined });
    try {
      if (!freshTab) await tab.page.evaluate(raw => {
        const data = JSON.parse(raw); SCStock.render(data, new Date('2026-09-11T13:35:00Z'));
        return SCStock.observations.bind(data, raw);
      }, revised);
      eq(kind + '/' + freshTab + ': byte revision retains independent positive facts', (await facts(tab.page)).restricted, ['burst:AAPL']);
      eq(kind + '/' + freshTab + ': previous sidecar cannot attach quote state', (await facts(tab.page)).generatedAt, null);
      eq(kind + '/' + freshTab + ': revised SHA remains exact', (await facts(tab.page)).recordHash, createHash('sha256').update(revised).digest('hex'));
      await tab.page.route('**/tests/fixtures/morning/full-publication.json', route => route.fulfill({ contentType: 'application/json', body: revised }));
      tab.response.status = 404;
      await tab.page.reload(); await wait(tab.page);
      eq(kind + '/' + freshTab + ': revised publication reload and 404 retain exclusion', await tab.page.locator('#detail [data-copy]').count(), 0);
      eq(kind + '/' + freshTab + ': cached facts never restore old quote receipt', (await facts(tab.page)).generatedAt, null);
    } finally { await tab.context.close(); }
  }

  for (const name of ['halted', 'corporate-excluded']) for (const width of [1280, 390]) for (const theme of ['dark', 'light']) {
    const tab = await setup(name, { width, theme });
    try {
      await tab.page.locator('#morning-open').click();
      check(name + '/' + width + '/' + theme + ': event refusal is prominent in Morning desk', (await tab.page.locator('#morning-desk h2').textContent()).includes('Entry withheld'));
      check(name + '/' + width + '/' + theme + ': event desk fits viewport', await tab.page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await tab.page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, `${name}-${width}-${theme}.png`) });
        await tab.page.locator('#morning-close').click();
        await tab.page.locator('#disc-observations > summary').click();
        await tab.page.locator('#detail').screenshot({ path: path.join(shotsDir, `${name}-detail-${width}-${theme}.png`) });
      }
    } finally { await tab.context.close(); }
  }

  for (const [name, edit] of [
    ['publication bytes', value => { value.publication.data_sha256 = '0'.repeat(64); }],
    ['same-session publication revision', value => { value.publication.published_at = '2026-09-10T23:00:00Z'; }],
    ['plan binding', value => { value.rows[0].plan_sha256 = '0'.repeat(64); }],
    ['candidate membership', value => { value.rows = []; }],
    ['rehearsal receipt', value => { value.dry_run = true; }],
    ['future receipt', value => { value.generated_at = '2026-09-11T13:40:00Z'; value.expires_at = '2026-09-11T13:45:00Z'; }],
    ['crossed quote', value => { value.rows[0].quote.ask = 1; }],
    ['unsafe source URL', value => { value.coverage.halts.source_url = 'javascript:alert(1)'; }]
  ]) {
    const current = await setup();
    try {
      const bad = structuredClone(records.observed); edit(bad);
      await current.reload(bad);
      eq(name + ': invalid observations rejected', (await facts(current.page)).state, 'unavailable');
      eq(name + ': source publication unchanged', await current.page.evaluate(() => JSON.stringify(SCStock.data)), JSON.stringify(publication));
    } finally { await current.context.close(); }
  }

  const bounded = await setup();
  try {
    await bounded.reload(JSON.stringify({ padding: '🧪'.repeat(140000) }));
    eq('decoded byte limit refuses oversized multibyte response', (await facts(bounded.page)).state, 'unavailable');
    check('oversized response names bounded refusal', (await bounded.page.locator('#disc-observations').textContent()).includes('size limit'));
    const captured = records['qeta-captured'];
    const result = await bounded.page.evaluate(captured => {
      const source = captured.coverage.halts, halt = captured.symbols.QETA.halt;
      try { SCStock.observations.validateHaltEvidence(halt, source, 'QETA', source.checked_at); } catch (e) { return { accepted: false, error: e.message }; }
      const changed = structuredClone(halt); changed.events[0].source_fields.HaltTime = '11:22:07.921';
      let refused = false;
      try { SCStock.observations.validateHaltEvidence(changed, source, 'QETA', source.checked_at); } catch (e) { refused = true; }
      return { accepted: true, refused };
    }, captured);
    eq('captured QETA fractional-second evidence validates exactly', result, { accepted: true, refused: true });
  } finally { await bounded.context.close(); }

  const late = await setup();
  try {
    await late.page.evaluate(() => { window.__previousPublicationCopy = document.querySelector('#detail .ss-action [data-copy]'); });
    late.response.body = JSON.stringify(records.halted); late.response.delay = 300;
    await late.page.evaluate(() => { void SCStock.observations.reload(); });
    await late.page.waitForFunction(() => __observationFetches.length >= 2);
    late.response.body = JSON.stringify(records['no-tickets']); late.response.delay = 0;
    const redRaw = await readFile(path.join(FIXTURES, 'red-publication.json'), 'utf8');
    await late.page.evaluate(raw => {
      const current = JSON.parse(raw);
      SCStock.render(current, new Date('2026-09-11T13:35:00Z'));
      void SCStock.observations.bind(current, raw);
    }, redRaw);
    await wait(late.page); await late.page.waitForTimeout(400);
    eq('late prior-publication response cannot replace the new binding', (await facts(late.page)).recordHash, createHash('sha256').update(redRaw).digest('hex'));
    eq('late response cannot transfer an old ticket observation', (await facts(late.page)).restricted, []);
    eq('new RED publication remains without order controls', await late.page.locator('#detail [data-copy]').count(), 0);
    await late.page.evaluate(() => window.__previousPublicationCopy.click());
    eq('detached copy control cannot copy a previous publication', await late.page.evaluate(() => __copies.length), 0);
  } finally { await late.context.close(); }

  const cryptoMissing = await setup('observed', { beforeLoad: page => page.addInitScript(() => { Object.defineProperty(crypto, 'subtle', { value: undefined }); }) });
  try {
    eq('missing WebCrypto cannot claim a verified receipt', (await facts(cryptoMissing.page)).state, 'unavailable');
    eq('missing WebCrypto makes no unbound sidecar request', cryptoMissing.requests.length, 0);
    check('missing WebCrypto explains exact verification is unavailable', (await cryptoMissing.page.locator('#disc-observations').textContent()).includes('Exact publication verification is unavailable'));
  } finally { await cryptoMissing.context.close(); }
}
