/* Explicit synthetic transport rehearsal. No service is deployed and no
   fixture becomes a current recommendation or a provider observation.

   Beside a configured morning host the page reads the same-origin static
   morning.json the morning workflow commits, on every read. This suite routes
   the two apart: `requests` are the host's, `staticRequests` the static
   file's, which is absent (a 404) unless a case publishes one. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { withEndpoint } from './offline_shell.mjs';
import { derive } from './reader_cases.mjs';
const ROOT = path.resolve(import.meta.dirname, '..');
const ENDPOINT = 'https://receipts.example.invalid/morning.json';
const NOW = '2026-09-11T13:35:00Z';
// how long before its pause the page's clock is installed (see setup())
const CLOCK_LEAD_MS = 60000;

export async function checkMorningServiceReader({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- optional morning receipt service: fixed private-free reads and bounded polling');
  const html = await readFile(path.join(ROOT, 'docs/index.html'), 'utf8');
  const raw = await readFile(path.join(ROOT, 'tests/fixtures/morning/full-publication.json'), 'utf8');
  const redRaw = await readFile(path.join(ROOT, 'tests/fixtures/morning/red-publication.json'), 'utf8');
  const observed = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/observed.json')));
  const halted = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/halted.json')));
  const resumed = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/resumed.json')));
  const outage = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/outage.json')));
  // a known corporate event on the one admitted plan, in a receipt without a halt
  const corporateExcluded = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/corporate-excluded.json')));
  // the same observed receipt, bound to the compact reader production loads
  const readerObserved = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/morning/reader-observed.json')));
  const facts = page => page.evaluate(() => SCStock.observations.facts());
  const wait = page => page.waitForFunction(() => ['loaded', 'unavailable', 'practice'].includes(SCStock.observations.facts().state));
  const hidden = (page, value) => page.evaluate(value => {
    Object.defineProperty(document, 'hidden', { configurable: true, value });
    document.dispatchEvent(new Event('visibilitychange'));
  }, value);
  const STATIC = base + '/docs/morning.json';
  const setup = async (options = {}) => {
    const endpoint = options.endpoint === undefined ? ENDPOINT : options.endpoint;
    const requests = [], response = { body: options.body !== undefined ? options.body : JSON.stringify(options.receipt || observed), status: options.status || 200, hold: options.hold || null, headers: {} };
    // With no endpoint the static file is the page's one source and stays in `requests`.
    const staticRequests = [], staticResponse = { body: options.staticReceipt ? JSON.stringify(options.staticReceipt) : 'not found', status: options.staticReceipt ? 200 : 404 };
    const tab = await open(browser, base, options.projected ? null : '/service-publication.json', options.pinned ? NOW : null, options.width || 1280, {
      theme: options.width === 390 ? 'light' : 'dark', hash: '#/explore/bursts/AAPL', reducedMotion: 'reduce',
      beforeLoad: async (page, context) => {
        // An installed clock runs in real time until it is paused. Installed AT
        // the instant it is paused at, a loaded runner that takes a tenth of a
        // second between the two calls has already passed that instant, and
        // pauseAt refuses to go back ("Cannot fast-forward to the past").
        // Installed a minute early, the pause is always a jump forward.
        const at = Date.parse(options.now || NOW);
        await page.clock.install({ time: new Date(at - CLOCK_LEAD_MS) });
        await page.clock.pauseAt(new Date(at));
        await context.addCookies([{ name: 'private_cookie', value: 'PRIVATE_SENTINEL', domain: 'receipts.example.invalid', path: '/', secure: true },
          { name: 'site_cookie', value: 'PRIVATE_SENTINEL', url: base + '/' }]);
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
        if (options.projected) {
          // The production load: the compact reader and its sidecar, never the canonical record.
          await page.route('**/reader.json*', route => route.fulfill({ contentType: 'application/json', body: options.projected.readerRaw }));
          await page.route('**/docs/data.json', route => route.fulfill({ status: 500, body: 'Canonical request forbidden in the projected control.' }));
          await page.route('**/reader-observations/*.json', route => route.fulfill({ contentType: 'application/json', body: options.projected.sidecarRaw }));
        }
        await page.route('**/morning.json', async route => {
          const seen = { url: route.request().url(), method: route.request().method(), body: route.request().postData(), headers: await route.request().allHeaders() };
          if (endpoint !== '' && seen.url === STATIC) {
            staticRequests.push(seen);
            return route.fulfill({ status: staticResponse.status, contentType: 'application/json', body: staticResponse.body }).catch(() => {});
          }
          requests.push(seen);
          const reply = { ...response };
          if (reply.hold) await reply.hold;
          await route.fulfill({ status: reply.status, contentType: 'application/json', body: reply.body, headers: { 'access-control-allow-origin': base, ...reply.headers } }).catch(() => {});
        });
      }
    });
    if (!options.hold) await wait(tab.page);
    const read = async () => { await tab.page.evaluate(() => SCStock.observations.reload()); await wait(tab.page); };
    return { ...tab, requests, response, staticRequests, staticResponse, read,
      // what each source has been asked so far: [the host, the static file]
      counts: () => [requests.length, staticRequests.length],
      // the static file the morning workflow would have committed (null: none published)
      publish(value, status) { staticResponse.body = value === null ? 'not found' : typeof value === 'string' ? value : JSON.stringify(value); staticResponse.status = status || (value === null ? 404 : 200); },
      async reload(value, status = 200) {
        response.body = typeof value === 'string' ? value : JSON.stringify(value); response.status = status;
        await read();
      } };
  };
  const summaryText = page => page.locator('#disc-observations').textContent();
  const sourceLine = async page => (await page.locator('#disc-observations [data-observation-source]').count()) ? (await page.locator('#disc-observations [data-observation-source]').textContent()).replace(/\s+/g, ' ').trim() : null;
  const offered = async page => (await page.locator('[data-observations="summary"] [data-observation-handoff]').count()) ? page.locator('[data-observations="summary"] [data-observation-handoff]').first().getAttribute('data-observation-handoff') : null;
  const workflowLinks = page => page.locator('[data-observations="summary"] [data-observation-workflow]').count();
  const FROM_HOST = 'Receipt source: the morning host.';
  const FROM_STATIC = 'Receipt source: the static morning file the morning workflow publishes.';
  const NO_NEWER = ' The morning host served no newer verified receipt for this record.';

  for (const width of [1280, 390]) {
    const tab = await setup({ width }), { page } = tab;
    try {
      eq(width + ': configured receipt validates against exact publication', [(await facts(page)).state, (await facts(page)).recordHash], ['loaded', createHash('sha256').update(raw).digest('hex')]);
      eq(width + ': the host receipt is the one shown, and the static file was read beside it', [(await facts(page)).source, await sourceLine(page), tab.counts()], ['host', FROM_HOST, [1, 1]]);
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
      eq(width + ': no early automatic request', tab.counts(), [1, 1]);
      await page.clock.runFor(2); await wait(page);
      eq(width + ': one automatic read of each file at 30 seconds', tab.counts(), [2, 2]);
      eq(width + ': automatic receipt changes apply their sourced halt', (await facts(page)).restricted, ['burst:AAPL']);
      eq(width + ': automatically observed halt withdraws entry copying', await page.locator('#detail [data-copy]').count(), 0);
      eq(width + ': polling preserves private cash draft and focus', await page.locator('#morning-cash').evaluate(n => [n.value, document.activeElement === n]), ['1234.', true]);
      eq(width + ': every request uses captured fixed endpoint with no private fields', tab.requests.map(r => [r.url, r.method, r.body, r.headers.cookie || null, r.headers.referer || null]), Array(2).fill([ENDPOINT, 'GET', null, null, null]));
      eq(width + ': every static read is the fixed same-origin file with no private fields, though the site holds a cookie', tab.staticRequests.map(r => [r.url, r.method, r.body, r.headers.cookie || null, r.headers.referer || null]), Array(2).fill([STATIC, 'GET', null, null, null]));
      eq(width + ': transport refuses redirects and credentials, on both files', await page.evaluate(() => __serviceFetches), Array(2).fill([
        { url: ENDPOINT, credentials: 'omit', redirect: 'error', mode: 'cors', referrerPolicy: 'no-referrer', body: null },
        { url: STATIC, credentials: 'omit', redirect: 'error', mode: 'same-origin', referrerPolicy: 'no-referrer', body: null }]).flat());
      const hint = await page.locator('[data-observations="summary"]').textContent();
      check(width + ': dynamic read and failure semantics are visible', /at most once every 30 seconds/.test(hint));
      check(width + ': the reload hint names both files and which receipt is shown', hint.includes('Reload reads the morning host’s receipt and the static morning file the morning workflow publishes, shows the newest one verified for this record'));
      eq(width + ': a host that holds this record is offered no hand-started run', [await offered(page), await workflowLinks(page)], [null, 0]);
      await hidden(page, true); await page.clock.runFor(90000);
      eq(width + ': hidden tab stops polling', tab.counts(), [2, 2]);
      await hidden(page, false); await page.clock.runFor(1); await wait(page);
      eq(width + ': becoming visible resumes one due read', tab.counts(), [3, 3]);
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
      const initial = tab.counts();
      await tab.page.clock.runFor(60000);
      eq(name + ': automatic reads remain off', tab.counts(), initial);
      if (name === 'static default') eq('empty deployment config retains exact static route, read once', tab.requests.map(r => r.url), [STATIC]);
      // One file is read there, so the summary prints no source line; the fact still says which file.
      if (name === 'static default') eq('empty deployment config: the one static file is shown and no receipt-source line is printed', [(await facts(tab.page)).state, (await facts(tab.page)).source, await sourceLine(tab.page)], ['loaded', 'static', null]);
      else if (name === 'practice') eq('practice requests no receipt', initial, [0, 0]);
      else eq(name + ': the one read asked each file once', initial, [1, 1]);
    } finally { await tab.context.close(); }
  }

  for (const endpoint of ['http://receipts.example.invalid/morning.json', ENDPOINT + '?ticker=AAPL', ENDPOINT + '#private', 'https://user:pass@receipts.example.invalid/morning.json', 'https://receipts.example.invalid/refresh', ENDPOINT + '?', ENDPOINT + '#', '//receipts.example.invalid/morning.json']) {
    const tab = await setup({ endpoint });
    try {
      eq('invalid endpoint refuses all network routes, the static file too: ' + endpoint, [tab.counts(), (await facts(tab.page)).state], [[0, 0], 'unavailable']);
      check('invalid endpoint explains configuration refusal', (await tab.page.locator('#disc-observations').textContent()).includes('configured morning receipt endpoint is invalid'));
    } finally { await tab.context.close(); }
  }

  const boundary = await setup({ now: '2026-09-11T12:59:45Z' });
  try {
    await boundary.page.clock.runFor(30001); await wait(boundary.page);
    eq('pre-open boundary starts polling through existing clock', boundary.counts(), [2, 2]);
    await boundary.page.clock.pauseAt(new Date('2026-09-11T13:59:45Z'));
    await boundary.page.evaluate(() => SCStock.reclock()); await boundary.page.clock.runFor(1); await wait(boundary.page);
    const count = boundary.counts();
    await boundary.page.clock.runFor(60000);
    eq('cutoff cancels future automatic reads', boundary.counts(), count);
    eq('cutoff removes entry authority', await boundary.page.evaluate(() => SCStock.avail.offered), false);
  } finally { await boundary.context.close(); }

  // The host answers 404 `no_receipt` naming the publication it holds, from the
  // evening's ingestion until the window's first cycle and after a revision.
  // The page reads the body before it refuses the status, says which case it
  // is and keeps polling inside the window. The static file is read beside it
  // and is absent here, so nothing is shown and each source is named beside
  // what it said. A 404 naming no publication says only that no file is
  // published. A host that does not hold this record leaves the hand-started
  // run on offer; one that holds it checks it itself.
  const publicationSha = createHash('sha256').update(raw).digest('hex');
  const noReceipt = sha => JSON.stringify({ publication_sha256: sha, status: 'no_receipt' });
  // a receipt valid in every way but bound to another publication
  const elsewhere = structuredClone(observed); elsewhere.publication.data_sha256 = 'e'.repeat(64);
  for (const [name, body, absent, headline, said] of [
    ['this record', noReceipt(publicationSha), 'none', 'No morning check yet for this record', 'No morning check has run for this publication yet; the morning host holds this record and no receipt for it.'],
    ['another publication', noReceipt('f'.repeat(64)), 'other', 'No morning check for this record', 'The morning host holds another publication, not this record, so no check for this record has run'],
    ['unnamed', 'not found', 'missing', 'No morning file published', 'The morning host answered that no file exists, without naming the publication it holds.'],
    ['unnamed JSON', JSON.stringify({ status: 'not_found' }), 'missing', 'No morning file published', 'without naming the publication it holds'],
    ['another status naming this record', JSON.stringify({ status: 'not_found', publication_sha256: publicationSha }), 'missing', 'No morning file published', 'without naming the publication it holds'],
    ['malformed digest', noReceipt('F'.repeat(64)), 'missing', 'No morning file published', 'without naming the publication it holds']
  ]) {
    const tab = await setup({ status: 404, body });
    try {
      const f = await facts(tab.page);
      eq('404 ' + name + ': the loaded record is the one the host would name', f.canonicalHash, publicationSha);
      eq('404 ' + name + ': the absence is read and named', [f.state, f.absent, f.headline, f.generatedAt], ['unavailable', absent, headline, null]);
      check('404 ' + name + ': the file status says why', (await tab.page.locator('#disc-observations').textContent()).includes(said));
      eq('404 ' + name + ': the summary carries the unavailable state', await tab.page.locator('#disc-observations').getAttribute('data-observation-state'), 'unavailable');
      eq('404 ' + name + ': each file is read once, at its own fixed address', [tab.requests.map(r => r.url), tab.staticRequests.map(r => r.url)], [[ENDPOINT], [STATIC]]);
      check('404 ' + name + ': the absent static file is named beside the host', (await summaryText(tab.page)).includes('Static morning file: No morning file is published beside this record.') && (await summaryText(tab.page)).includes('Morning host: '));
      if (absent === 'none') eq('404 ' + name + ': a host that holds this record is offered no hand-started run', [await offered(tab.page), await workflowLinks(tab.page)], [null, 0]);
      else eq('404 ' + name + ': a host that does not hold this record leaves the hand-started run on offer', [await offered(tab.page), await workflowLinks(tab.page)], ['due', 1]);
      const before = tab.counts();
      await tab.page.clock.runFor(31000); await wait(tab.page);
      eq('404 ' + name + ': polling continues inside the window, on both files', tab.counts(), before.map(n => n + 1));
      await tab.reload(observed);
      eq('404 ' + name + ': the first receipt of the window replaces the absence', [(await facts(tab.page)).state, (await facts(tab.page)).absent, (await facts(tab.page)).source], ['loaded', null, 'host']);
      eq('404 ' + name + ': and withdraws the offer, the host holding the record now', await offered(tab.page), null);
    } finally { await tab.context.close(); }
  }
  if (shotsDir) {
    // The phone's desk over the evening's answer, for a reader to look at.
    const tab = await setup({ status: 404, body: noReceipt(publicationSha), width: 390 });
    try {
      await tab.page.locator('#morning-open').click();
      await tab.page.waitForTimeout(250);
      await mkdir(shotsDir, { recursive: true });
      await tab.page.screenshot({ path: path.join(shotsDir, 'morning-service-no-receipt-390.png'), fullPage: false });
      eq('404 this record at 390: the desk is open over the absence', [(await facts(tab.page)).absent, await tab.page.locator('#disc-observations').isVisible()], ['none', true]);
    } finally { await tab.context.close(); }
  }
  // The production load is the compact reader: recordHash is the reader's
  // digest and the host names the canonical one, so the comparison is against
  // the canonical digest, and a 404 naming the reader's is another publication.
  {
    const projected = derive(raw);
    const readerSha = createHash('sha256').update(projected.readerRaw).digest('hex');
    for (const [name, named, absent] of [['canonical', publicationSha, 'none'], ['reader', readerSha, 'other']]) {
      const tab = await setup({ status: 404, body: noReceipt(named), projected });
      try {
        const f = await facts(tab.page);
        eq('projected 404 naming the ' + name + ' digest: the page loaded the compact reader', [f.projected, f.canonicalHash === publicationSha, f.recordHash === readerSha, readerSha !== publicationSha], [true, true, true, true]);
        eq('projected 404 naming the ' + name + ' digest: compared against the canonical digest', [f.state, f.absent], ['unavailable', absent]);
      } finally { await tab.context.close(); }
    }
  }
  // ---- two sources: the morning host and the same-origin static file -------
  // Each file is held to the loaded publication by the page's own validation.
  // The newest verified receipt is shown (the host's on a tie) and names its
  // source; a receipt bound to another publication is never shown; positive
  // halt facts are kept from both; the newest verified file omitting a
  // restriction the other carries is refused; and the hand-started run is
  // offered only when the host's answer shows it does not hold this record.
  {
    const AFTER = '2026-09-11T13:36:00Z';   // past the resumed receipt's 13:35:30
    const later = (receipt, seconds) => {
      const value = structuredClone(receipt), plus = stamp => new Date(Date.parse(stamp) + seconds * 1000).toISOString();
      value.generated_at = plus(value.generated_at); value.expires_at = plus(value.expires_at); return value;
    };
    const shown = async page => { const f = await facts(page); return [f.state, f.absent, f.source, f.generatedAt, f.restricted]; };
    const OMITTED = 'A previous event exclusion was omitted without a sourced resolution; it remains withheld.';
    const two = async (name, options, want, extra) => {
      const tab = await setup(options);
      try {
        eq('two sources / ' + name, await shown(tab.page), want);
        eq('two sources / ' + name + ': each file was read once', tab.counts(), [1, 1]);
        if (extra) await extra(tab, 'two sources / ' + name + ': ');
        eq('two sources / ' + name + ': no browser errors', [...tab.errors], []);
      } finally { await tab.context.close(); }
    };
    // the open desk with its observation summary at the top, for a reader to look at
    const deskShot = async (page, name) => {
      await page.locator('#morning-open').click(); await page.waitForTimeout(250);
      await page.locator('[data-observations="summary"]').evaluate(node => node.scrollIntoView({ block: 'start' }));
      await mkdir(shotsDir, { recursive: true });
      await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, name) });
      await page.locator('#morning-close').click();
    };
    // One poll at a time, each read settled before the clock moves again: a
    // long run of the paused clock would reach a read's own 15-second limit
    // while its routed answer is still on the way, and abort it.
    const cycles = async (tab, count) => { for (let i = 0; i < count; i++) { await tab.page.clock.runFor(30001); await wait(tab.page); } };
    // eleven polls on: past the static receipt's five minutes, still inside the entry window
    const expire = async tab => { await cycles(tab, 11); return (await facts(tab.page)).fresh; };

    // The deployed state on 19 November 2026: the host answers 200 with a
    // receipt for an older publication, and the morning workflow has
    // committed a static receipt for this one.
    for (const width of [1280, 390]) {
      await two(width + ': the host serves a receipt bound to another publication, the static file is bound', { width, receipt: elsewhere, staticReceipt: observed }, ['loaded', null, 'static', observed.generated_at, []], async (tab, label) => {
        const { page } = tab;
        eq(label + 'the summary names the static file and says the host served nothing newer', await sourceLine(page), FROM_STATIC + NO_NEWER);
        check(label + 'entry copying is offered as under any bound receipt', (await page.locator('#detail [data-copy]').count()) > 0);
        eq(label + 'a current check offers no hand-started run', [await offered(page), await workflowLinks(page)], [null, 0]);
        if (shotsDir) await deskShot(page, `morning-service-static-${width}.png`);
        await page.clock.runFor(30001); await wait(page);
        eq(label + 'polling reads both files each cycle', tab.counts(), [2, 2]);
        eq(label + 'once the static receipt has expired the run is offered, the host not holding this record', [await expire(tab), await offered(page), await workflowLinks(page)], [false, 'expired', 1]);
        if (shotsDir) await deskShot(page, `morning-service-static-expired-${width}.png`);
        // then the static file cannot be read: its receipt is retained with its
        // source, the sentence about the host is not repeated for a read that
        // did not happen, and an unreadable file leaves the answer unknown
        tab.publish('{', 200); await tab.read();
        eq(label + 'an unreadable static file retains its last receipt and source', await shown(page), ['unavailable', null, 'static', observed.generated_at, []]);
        eq(label + 'the retained static receipt names its source alone', await sourceLine(page), FROM_STATIC);
        eq(label + 'a static file that could not be read leaves the answer unknown, so nothing is offered', await offered(page), null);
      });
    }
    await two('the host names another publication (404), the static file is bound', { status: 404, body: noReceipt('f'.repeat(64)), staticReceipt: observed }, ['loaded', null, 'static', observed.generated_at, []], async (tab, label) => {
      eq(label + 'after expiry the run is offered', [await expire(tab), await offered(tab.page)], [false, 'expired']);
    });
    await two('the host cannot be read (503), the static file is bound', { status: 503, body: '{"status":"unavailable"}', staticReceipt: observed }, ['loaded', null, 'static', observed.generated_at, []], async (tab, label) => {
      eq(label + 'the summary still names the static file', await sourceLine(tab.page), FROM_STATIC + NO_NEWER);
      eq(label + 'what the host holds is unknown, so no run is offered even after expiry', [await expire(tab), await offered(tab.page), await workflowLinks(tab.page)], [false, null, 0]);
    });
    await two('the host holds this record and has no check yet (404), the static file is bound', { status: 404, body: noReceipt(publicationSha), staticReceipt: observed }, ['loaded', null, 'static', observed.generated_at, []], async (tab, label) => {
      eq(label + 'a host that holds the record checks it itself: no run is offered even after expiry', [await expire(tab), await offered(tab.page), await workflowLinks(tab.page)], [false, null, 0]);
    });
    await two('the host is bound, the static file is bound to another publication', { receipt: observed, staticReceipt: elsewhere }, ['loaded', null, 'host', observed.generated_at, []], async (tab, label) => {
      eq(label + 'the summary names the host', await sourceLine(tab.page), FROM_HOST);
      // A host that served this record's receipt holds the record: once that
      // receipt has expired it is still the host's to check, and no run is offered.
      eq(label + 'a host whose receipt for this record has expired is still offered no hand-started run', [await expire(tab), (await facts(tab.page)).source, await offered(tab.page), await workflowLinks(tab.page)], [false, 'host', null, 0]);
    });
    await two('both files are bound to another publication: nothing is shown', { receipt: elsewhere, staticReceipt: elsewhere }, ['unavailable', 'other', null, null, []], async (tab, label) => {
      check(label + 'each refusal is named by its source', (await summaryText(tab.page)).includes('Morning host: These observations belong to another publication. Static morning file: These observations belong to another publication.'));
      eq(label + 'no receipt time and no source line are printed', [await tab.page.locator('#disc-observations [data-observation-time]').count(), await sourceLine(tab.page)], [0, null]);
      eq(label + 'the absence is known and the host does not hold this record, so the run is offered', [await offered(tab.page), await workflowLinks(tab.page)], ['due', 1]);
    });
    await two('the host cannot be read (503) and the static file is absent: the absence is not known', { status: 503, body: '{"status":"unavailable"}' }, ['unavailable', null, null, null, []], async (tab, label) => {
      eq(label + 'the headline claims no absence, and nothing is offered', [(await facts(tab.page)).headline, await offered(tab.page)], ['Morning observations unavailable', null]);
      check(label + 'each file is named beside what it said', (await summaryText(tab.page)).includes('Morning host: The published morning file could not be read. Static morning file: No morning file is published beside this record.'));
    });
    // Positive facts are kept from both files: the host alone carries the
    // halt and the static file alone the event exclusion, so neither file
    // carries every fact the tab now holds, and the host's receipt (the tie's
    // winner) omits the exclusion and is refused.
    await two('a halt only the host carries and an event exclusion only the static file carries are both kept', { receipt: halted, staticReceipt: corporateExcluded }, ['unavailable', null, null, null, ['burst:AAPL']], async (tab, label) => {
      const text = await summaryText(tab.page);
      check(label + 'the event exclusion withholds entry copying', text.includes('Morning corporate-event exclusion') && (await tab.page.locator('#detail [data-copy]').count()) === 0);
      check(label + 'the reload cache says neither file carried every fact', text.includes('Reload coverage: Neither published morning file carries every source fact this tab retains, so neither was saved for reloads.'));
      check(label + 'the omission is refused in the existing words', text.includes(OMITTED));
      // the static file alone, on a fresh tab, would have been shown with its exclusion
    });
    await two('a tie goes to the host, and its halt applies', { receipt: halted, staticReceipt: observed }, ['loaded', null, 'host', halted.generated_at, ['burst:AAPL']], async (tab, label) => {
      check(label + 'no reload-coverage line when the other file lacks the halt', !(await summaryText(tab.page)).includes('Reload coverage:'));
      eq(label + 'the halt withdraws entry copying', await tab.page.locator('#detail [data-copy]').count(), 0);
    });
    await two('a tie goes to the host, but a halt only the static file carries is kept and the read refused', { receipt: observed, staticReceipt: halted }, ['unavailable', null, null, null, ['burst:AAPL']], async (tab, label) => {
      check(label + 'the omission is refused in the existing words', (await summaryText(tab.page)).includes(OMITTED));
      eq(label + 'the kept halt withdraws entry copying', await tab.page.locator('#detail [data-copy]').count(), 0);
      await tab.page.clock.runFor(30001); await wait(tab.page);
      eq(label + 'the next read of the same two files refuses again', [await shown(tab.page), tab.counts()], [['unavailable', null, null, null, ['burst:AAPL']], [2, 2]]);
    });
    await two('the newest verified file omits a halt an older static file carries: refused, the older file is not shown in its place', { now: AFTER, receipt: later(observed, 30), staticReceipt: halted }, ['unavailable', null, null, null, ['burst:AAPL']], async (tab, label) => {
      check(label + 'the omission is refused in the existing words', (await summaryText(tab.page)).includes(OMITTED));
    });
    await two('the newest wins: the host records a sourced resumption after the static file’s halt', { now: AFTER, receipt: resumed, staticReceipt: halted }, ['loaded', null, 'host', resumed.generated_at, []], async (tab, label) => {
      const { page } = tab;
      // Six polls on (13:39:00), the resumption's own halt source has
      // expired (13:38:30) and the receipt is still inside its five minutes:
      // the unchanged static file is read on every cycle and its halt is not
      // taken again.
      await cycles(tab, 6);
      eq(label + 'the resumption stays recorded while the unchanged static file is read again', [await shown(page), (await facts(page)).fresh, tab.counts()], [['loaded', null, 'host', resumed.generated_at, []], true, [7, 7]]);
      // the same halt in a file whose text changed is new evidence: taken
      // again, and a resumption whose halt source has expired cannot clear it
      tab.publish(JSON.stringify(halted, null, 1)); await tab.read();
      eq(label + 'a changed static file is taken again and its halt kept', await shown(page), ['unavailable', null, 'host', resumed.generated_at, ['burst:AAPL']]);
      check(label + 'that refusal is the existing sentence', (await summaryText(page)).includes(OMITTED));
    });
    await two('the newest wins: a static receipt newer than the host’s', { now: AFTER, receipt: observed, staticReceipt: resumed }, ['loaded', null, 'static', resumed.generated_at, []], async (tab, label) => {
      eq(label + 'the summary names the static file', await sourceLine(tab.page), FROM_STATIC + NO_NEWER);
    });
    await two('a newer static receipt replaces an older static one', { now: AFTER, receipt: elsewhere, staticReceipt: observed }, ['loaded', null, 'static', observed.generated_at, []], async (tab, label) => {
      tab.publish(resumed); await tab.read();
      eq(label + 'the newer file is shown', await shown(tab.page), ['loaded', null, 'static', resumed.generated_at, []]);
      // and an older host receipt, bound to this record, cannot replace it
      tab.publish(null); await tab.reload(observed);
      eq(label + 'an older host receipt cannot replace a newer verified static one', await shown(tab.page), ['unavailable', null, 'static', resumed.generated_at, []]);
      check(label + 'the refusal is the existing sentence, and the absent static file is named beside it', (await summaryText(tab.page)).includes('File status: An older observation file was not loaded. Static morning file: No morning file is published beside this record.'));
    });
    await two('an older static receipt cannot replace a newer verified host receipt', { now: AFTER, receipt: resumed, staticReceipt: observed }, ['loaded', null, 'host', resumed.generated_at, []], async (tab, label) => {
      await tab.reload('{}', 503);
      eq(label + 'the host fails and the older static file is refused', await shown(tab.page), ['unavailable', null, 'host', resumed.generated_at, []]);
      check(label + 'the refusal is the existing sentence, and the failed host read is named beside it', (await summaryText(tab.page)).includes('File status: An older observation file was not loaded. Morning host: The published morning file could not be read.'));
    });
    await two('the shown receipt always carries its own halt, taken before or not', { now: AFTER, receipt: resumed, staticReceipt: halted }, ['loaded', null, 'host', resumed.generated_at, []], async (tab, label) => {
      // The host's resumption cleared the static file's halt. The host then
      // fails and the same record is bound again, so the unchanged static
      // file is the one receipt verified: it is shown, with its halt.
      tab.response.body = '{}'; tab.response.status = 503;
      await tab.page.evaluate(raw => { const data = JSON.parse(raw); SCStock.render(data); return SCStock.observations.bind(data, raw); }, raw); await wait(tab.page);
      eq(label + 'the static receipt is shown with the halt it carries', await shown(tab.page), ['loaded', null, 'static', halted.generated_at, ['burst:AAPL']]);
      eq(label + 'and entry copying is withheld', await tab.page.locator('#detail [data-copy]').count(), 0);
    });
    // The compact reader is how production loads: the static receipt names
    // the reader's digest beside the canonical one.
    await two('the compact reader: the host names another publication, the static receipt is bound to the reader', { status: 404, body: noReceipt('f'.repeat(64)), projected: derive(raw), staticReceipt: readerObserved }, ['loaded', null, 'static', readerObserved.generated_at, []], async (tab, label) => {
      eq(label + 'the page loaded the compact reader', (await facts(tab.page)).projected, true);
    });
    // One request limit covers both files: a host that never answers holds
    // the static receipt back until the 15-second bound, and no longer.
    let release;
    const slow = await setup({ hold: new Promise(resolve => { release = resolve; }), staticReceipt: observed });
    try {
      await slow.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
      eq('two sources / an unanswered host: the read is still pending, and entry copying is paused', [(await facts(slow.page)).pending, slow.counts(), await slow.page.locator('#detail [data-copy]').count()], [true, [1, 1], 0]);
      await slow.page.clock.runFor(15000); await wait(slow.page);
      eq('two sources / an unanswered host: at the request bound the static receipt is shown', await shown(slow.page), ['loaded', null, 'static', observed.generated_at, []]);
      check('two sources / an unanswered host: entry copying returns with the bound receipt', (await slow.page.locator('#detail [data-copy]').count()) > 0);
    } finally { release(); await slow.context.close(); }
  }

  const retained = await setup({ receipt: halted });
  try {
    const checked = (await facts(retained.page)).generatedAt;
    for (const [name, body, status] of [
      ['malformed', '{', 200], ['outage', '{}', 503], ['omitted restriction', observed, 200],
      ['oversized', JSON.stringify({ padding: 'x'.repeat(512 * 1024) }), 200],
      ['no receipt yet', JSON.stringify({ publication_sha256: publicationSha, status: 'no_receipt' }), 404]
    ]) {
      const asked = retained.counts();
      await retained.reload(body, status);
      eq(name + ': last verified receipt and halt remain', [(await facts(retained.page)).state, (await facts(retained.page)).generatedAt, (await facts(retained.page)).source, (await facts(retained.page)).restricted], ['unavailable', checked, 'host', ['burst:AAPL']]);
      eq(name + ': the failed host read asked the static file too, once', retained.counts(), asked.map(n => n + 1));
      // The static file now carries a receipt bound to this record that omits
      // the halt, and one bound elsewhere: neither replaces the retained
      // receipt, and neither clears the halt.
      for (const [what, published] of [['a bound static receipt that omits the halt', observed], ['a static receipt bound to another publication', elsewhere]]) {
        retained.publish(published); await retained.read();
        eq(name + ', beside ' + what + ': the retained receipt and its halt stand', [(await facts(retained.page)).state, (await facts(retained.page)).generatedAt, (await facts(retained.page)).source, (await facts(retained.page)).restricted], ['unavailable', checked, 'host', ['burst:AAPL']]);
      }
      eq(name + ': the retained receipt still names the host as its source', await sourceLine(retained.page), FROM_HOST);
      retained.publish(null); await retained.read();
    }
    eq('no receipt yet: the absence is known beside the retained receipt', [(await facts(retained.page)).absent, (await facts(retained.page)).headline], ['none', 'No morning check yet for this record']);
    await retained.page.clock.runFor(361000); await wait(retained.page);
    eq('old retained receipt remains visibly expired', (await facts(retained.page)).fresh, false);
    eq('expired restriction still withholds copying', await retained.page.locator('#detail [data-copy]').count(), 0);
  } finally { await retained.context.close(); }

  for (const [kind, phrase] of [['local_interval', 'this feed was polled less than its minimum spacing ago, so the cycle skipped it; the previous reading stands.'], ['local_budget', 'today\u2019s request budget for this feed is spent.'], ['local_backoff', 'backoff after earlier provider failure.']]) {
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
    eq('clock and page-restoration bursts do not multiply inflight requests', late.counts(), [2, 2]);
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
    eq('a redirect cannot change either fixed destination', [redirect.requests.map(r => r.url), redirect.staticRequests.map(r => r.url)], [[ENDPOINT, ENDPOINT], [STATIC, STATIC]]);
    eq('redirect failure preserves last verified receipt', [(await facts(redirect.page)).state, (await facts(redirect.page)).generatedAt], ['unavailable', observed.generated_at]);
  } finally { await redirect.context.close(); }

  const cutting = await setup({ now: '2026-09-11T13:59:25Z' });
  let releaseCutoff;
  try {
    cutting.response.hold = new Promise(resolve => { releaseCutoff = resolve; });
    await cutting.page.clock.runFor(30001);
    await cutting.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
    await cutting.page.clock.runFor(5000);
    eq('cutoff aborts an inflight automatic request before its ordinary timeout', [(await facts(cutting.page)).state, cutting.counts()], ['unavailable', [2, 2]]);
  } finally { if (releaseCutoff) releaseCutoff(); await cutting.context.close(); }

  const timeout = await setup();
  let releaseTimeout;
  try {
    timeout.response.hold = new Promise(resolve => { releaseTimeout = resolve; });
    await timeout.page.clock.runFor(30001);
    await timeout.page.waitForFunction(() => SCStock.observations.facts().state === 'loading');
    await timeout.page.clock.runFor(15000); await wait(timeout.page);
    eq('configured transport keeps the 15-second request bound', [(await facts(timeout.page)).state, (await facts(timeout.page)).generatedAt], ['unavailable', observed.generated_at]);
    eq('bounded timeout does not immediately retry', timeout.counts(), [2, 2]);
  } finally { if (releaseTimeout) releaseTimeout(); await timeout.context.close(); }
}
