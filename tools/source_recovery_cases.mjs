/* The Method view's one source-recovery line: the receipt's own sentence, printed
   only once the receipt has been held to the record on screen by its bytes and
   its identity (`recoveryOf()`), and otherwise one sentence saying what is absent.
   The page adds no figure, no chip and no control. The records are the `thin`
   page fixture (QAA stale, ending 9 September) and the generator's `full` night;
   the receipts are the source-recovery fixtures, the collector's own output over
   those records with a pinned clock and the suite's Alpaca double, routed under
   the page's own file name. Lane B: writes no scratch record, reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';

const PAGE = path.resolve('tests/fixtures/page');
const RECEIPTS = path.resolve('tests/fixtures/source-recovery');
// 8:20 Chicago on Friday 11 Sep 2026, the thin night's recovery slot
const FRESH = '2026-09-11T13:20:00Z';
const clone = (d) => JSON.parse(JSON.stringify(d));
const sha = (raw) => createHash('sha256').update(raw).digest('hex');
const python = process.env.SCSTOCK_PYTHON || 'python3';
// the compact reader the publication step derives from a canonical record, so a
// case can load the record the way production serves it
function readerOf(raw) {
  return execFileSync(python, ['-c', 'import sys\nfrom src.reader import derive\nsys.stdout.buffer.write(derive(sys.stdin.buffer.read())[0])'],
    { cwd: path.resolve('.'), input: raw, maxBuffer: 64 * 1024 * 1024 });
}
const PREFIX = 'Recovery: ';

function served(body, status = 200) {
  return (p) => p.route('**/source-recovery.json', (route) => status === 200
    ? route.fulfill({ contentType: 'application/json', body })
    : status === 'abort' ? route.abort('failed')
    : route.fulfill({ status, contentType: 'text/plain', body: 'absent' }));
}
const recoveryLine = async (page) => {
  const li = page.locator('#run-meta li[data-source-recovery]');
  // a line that never settles is reported as 'loading' and fails its own check, never a thrown timeout
  await page.waitForFunction(() => { const n = document.querySelector('#run-meta li[data-source-recovery]'); return n && n.getAttribute('data-source-recovery') !== 'loading'; }, null, { timeout: 15000 }).catch(() => {});
  return { text: await li.innerText(), state: await li.getAttribute('data-source-recovery'), count: await li.count() };
};

export async function checkSourceRecovery({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- source recovery: the Method line prints the bound receipt and nothing else');
  const thin = JSON.parse(await readFile(path.join(PAGE, 'thin.json'), 'utf8'));
  const recovered = JSON.parse(await readFile(path.join(RECEIPTS, 'thin-recovered.json'), 'utf8'));
  const inapplicable = JSON.parse(await readFile(path.join(RECEIPTS, 'thin-inapplicable.json'), 'utf8'));
  const production = JSON.parse(await readFile(path.join(RECEIPTS, 'recovered.json'), 'utf8'));
  check('the thin receipt is the collector\'s over the thin night', recovered.status === 'recovered' && recovered.rows.length === 1 && recovered.rows[0].ticker === 'QAA' && recovered.dry_run === true, JSON.stringify([recovered.status, recovered.rows.map(r => r.ticker)]));
  check('the thin fixture names the stale stock the receipt asked for', thin.run.input_tolerance.names.join() === 'QAA');

  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [320, 'dark']]) {
    const where = `${width} ${theme}`;
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin.json', FRESH, width,
      { height: width < 400 ? 844 : 900, theme, reducedMotion: 'reduce', lens: 'all', hash: '#/method', beforeLoad: served(JSON.stringify(recovered)) });
    try {
      eq(`${where}: fresh`, await page.getAttribute('html', 'data-ss-rendered'), 'fresh');
      const got = await recoveryLine(page);
      eq(`${where}: one line, in the receipt's own status`, [got.count, got.state], [1, 'recovered']);
      eq(`${where}: the line is the receipt's sentence verbatim`, got.text, PREFIX + recovered.sentence);
      check(`${where}: the sentence names the stock and adds no coverage figure of the page's own`, got.text.includes('its 1 stock without a usable 2026-09-10 bar') && got.text.includes('99 of 100 intended stocks ready') && !/100 of 100/.test(got.text), got.text);
      const requests = await page.evaluate(() => performance.getEntriesByType('resource').filter(e => /source-recovery\.json/.test(e.name)).length);
      eq(`${where}: the receipt was fetched once, when Method was shown`, requests, 1);
      // a second render of the Method view does not fetch the file again
      await page.evaluate(() => { location.hash = '#/record'; }); await page.waitForTimeout(150);
      await page.evaluate(() => { location.hash = '#/method'; }); await page.waitForTimeout(250);
      eq(`${where}: and a route back to Method fetches nothing more`, await page.evaluate(() => performance.getEntriesByType('resource').filter(e => /source-recovery\.json/.test(e.name)).length), 1);
      check(`${where}: no chip, control or figure was added for it`, (await page.locator('#run-meta li[data-source-recovery] button, #run-meta li[data-source-recovery] a, #run-meta li[data-source-recovery] .sc-chip').count()) === 0);
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      const body = await page.locator('body').innerText();
      check(`${where}: nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('#run-details').screenshot({ path: path.join(shotsDir, `source-recovery-${width}-${theme}.png`) }); }
      eq(`${where}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- the receipt is asked for only when the Method view is shown: the default
  // route, Explore and Record fetch nothing, so no other suite sees a request for it
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin.json', FRESH, 1280,
      { reducedMotion: 'reduce', lens: 'all', beforeLoad: served(JSON.stringify(recovered)) });
    try {
      const fetched = () => page.evaluate(() => performance.getEntriesByType('resource').filter(e => /source-recovery\.json/.test(e.name)).length);
      eq('default route: the receipt is not fetched', await fetched(), 0);
      eq('default route: the Method line waits', await page.getAttribute('#run-meta li[data-source-recovery]', 'data-source-recovery'), 'loading');
      await page.evaluate(() => { location.hash = '#/record'; }); await page.waitForTimeout(250);
      eq('Record view: still not fetched', await fetched(), 0);
      await page.evaluate(() => { location.hash = '#/method'; }); await page.waitForTimeout(250);
      const got = await recoveryLine(page);
      eq('Method shown: fetched once and settled', [await fetched(), got.state], [1, 'recovered']);
      eq('deferred-fetch page errors', [...errors], []);
    } finally { await context.close(); }
  }

  // ---- an inapplicable receipt prints its one sentence; a missing file and
  // every unbound shape print what is absent and never the receipt's words
  const unbound = (mutate, why) => { const r = clone(recovered); mutate(r); return [r, why]; };
  const cases = [
    ['inapplicable', JSON.stringify(inapplicable), 200, 'inapplicable', PREFIX + inapplicable.sentence],
    ['absent', '', 404, 'absent', PREFIX + 'no receipt has been published beside this record.'],
    // only a 404 says no receipt exists: a server error, no answer and a body that
    // is not JSON say the receipt could not be read
    ['server error', '', 500, 'unreadable', PREFIX + 'the published receipt could not be read (HTTP 500).'],
    ['no answer', '', 'abort', 'unreadable', PREFIX + 'the published receipt could not be read (no answer).'],
    ['truncated', JSON.stringify(recovered).slice(0, 200), 200, 'unreadable', PREFIX + 'the published receipt could not be read (its body is not JSON).'],
    ['another-publication', JSON.stringify(production), 200, 'unbound', 'another publication’s bytes'],
    ...[
      unbound(r => { r.publication.data_sha256 = '0'.repeat(64); }, 'another publication’s bytes'),
      unbound(r => { r.publication.rules_version = 'other'; }, 'another publication’s identity'),
      unbound(r => { r.publication.measured_session = '2026-09-09'; }, 'another publication’s identity'),
      unbound(r => { r.publication.context_sha256 = 'e'.repeat(64); }, 'another publication’s identity'),
      unbound(r => { r.publication.published_at = '2026-09-10T23:00:00+00:00'; }, 'another publication’s identity'),
      unbound(r => { r.status = 'ready'; }, 'unknown status'),
      unbound(r => { r.sentence = ''; }, 'no sentence'),
      unbound(r => { r.schema_version = 2; }, 'unsupported schema'),
      unbound(r => { delete r.publication; }, 'no publication binding'),
    ].map(([r, why]) => [why, JSON.stringify(r), 200, 'unbound', why]),
  ];
  for (const [name, body, status, state, words] of cases) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin.json', FRESH, 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/method', beforeLoad: served(body, status) });
    try {
      const got = await recoveryLine(page);
      eq(`${name}: the line's state`, got.state, state);
      check(`${name}: the line says ${words.slice(0, 60)}`, got.text.includes(words), got.text);
      if (state !== 'inapplicable') check(`${name}: and prints none of the receipt's own words`, !got.text.includes('asked for again'), got.text);
      if (state === 'unreadable') check(`${name}: and never says that no receipt was published`, !got.text.includes('no receipt has been published'), got.text);
      eq(`${name}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- a production receipt (dry_run false) over a fixture page is another
  // publication's; a rehearsal receipt is admitted only over a fixture page, which
  // the full night is, with no deficit to recover
  const noDeficit = JSON.parse(await readFile(path.join(RECEIPTS, 'no-deficit.json'), 'utf8'));
  const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH, 1280,
    { reducedMotion: 'reduce', lens: 'all', hash: '#/method', beforeLoad: served(JSON.stringify(noDeficit)) });
  try {
    const got = await recoveryLine(page);
    eq('no deficit: the receipt binds and says why nothing was fetched', [got.state, got.text], ['inapplicable', PREFIX + noDeficit.sentence]);
    const read = await page.evaluate(([receipt]) => { const r = window.SCStock.recoveryOf(receipt, window.SCStock.data, null); return [r.known, r.why]; }, [noDeficit]);
    eq('recoveryOf refuses a receipt it cannot hold to the record\'s bytes', read, [false, 'another publication’s bytes']);
    eq('page errors', [...errors], []);
  } finally { await context.close(); }

  // ---- the same record drawn again (the public SCStock.render) settles its new
  // Method line from the receipt already fetched: one request, never a line left loading
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin.json', FRESH, 1280,
      { reducedMotion: 'reduce', lens: 'all', hash: '#/method', beforeLoad: served(JSON.stringify(recovered)) });
    try {
      const fetched = () => page.evaluate(() => performance.getEntriesByType('resource').filter(e => /source-recovery\.json/.test(e.name)).length);
      eq('redraw: settled before', (await recoveryLine(page)).state, 'recovered');
      await page.evaluate(() => { window.SCStock.render(window.SCStock.data, new Date(window.SCStock.now)); });
      await page.evaluate(() => { location.hash = '#/record'; }); await page.waitForTimeout(150);
      await page.evaluate(() => { location.hash = '#/method'; }); await page.waitForTimeout(250);
      const got = await recoveryLine(page);
      eq('redraw: the new line settles from the fetched receipt', [got.count, got.state, got.text], [1, 'recovered', PREFIX + recovered.sentence]);
      eq('redraw: and nothing was fetched again', await fetched(), 1);
      eq('redraw: page errors', [...errors], []);
    } finally { await context.close(); }
  }
  // ---- production loads the compact reader: the receipt is held to the
  // canonical digest the projection names AND the hash of the reader bytes served
  {
    const thinRaw = await readFile(path.join(PAGE, 'thin.json'));
    const projection = readerOf(thinRaw);
    eq('the thin receipt names the reader the publication step derives', recovered.publication.reader_sha256, sha(projection));
    const servedReader = (body) => (p) => p.route('**/docs/reader.json*', (route) => route.fulfill({ contentType: 'application/json', body }));
    const forged = clone(recovered); forged.publication.reader_sha256 = 'f'.repeat(64);
    for (const [name, receipt, state, words] of [
      ['projected', recovered, 'recovered', PREFIX + recovered.sentence],
      ['projected, another reader', forged, 'unbound', 'another publication’s bytes'],
    ]) {
      const { page, context, errors } = await open(browser, base, null, FRESH, 1280, { reducedMotion: 'reduce', lens: 'all', hash: '#/method',
        beforeLoad: async (pg) => { await servedReader(projection)(pg); await served(JSON.stringify(receipt))(pg); } });
      try {
        eq(`${name}: the page loaded the projection`, await page.evaluate(() => window.SCStock.reader.status().projected), true);
        const got = await recoveryLine(page);
        eq(`${name}: the line's state`, got.state, state);
        check(`${name}: the line says ${words.slice(0, 60)}`, got.text.includes(words), got.text);
        eq(`${name}: page errors`, [...errors], []);
      } finally { await context.close(); }
    }
  }

  // ---- a rehearsal receipt is admitted over a fixture page only: the same thin
  // record without its fixture mark, its receipt rebound to those bytes, is refused
  {
    const live = JSON.parse(await readFile(path.join(PAGE, 'thin.json'), 'utf8'));
    delete live.fixture;
    const body = JSON.stringify(live);
    const rebound = clone(recovered); rebound.publication.data_sha256 = sha(body);
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin-live.json', FRESH, 1280, { reducedMotion: 'reduce', lens: 'all', hash: '#/method',
      beforeLoad: async (pg) => { await pg.route('**/thin-live.json', (route) => route.fulfill({ contentType: 'application/json', body })); await served(JSON.stringify(rebound))(pg); } });
    try {
      const got = await recoveryLine(page);
      eq('a rehearsal over the live record: unbound', got.state, 'unbound');
      check('a rehearsal over the live record: says why', got.text.includes('a rehearsal receipt'), got.text);
      eq('rehearsal page errors', [...errors], []);
    } finally { await context.close(); }
  }

  // ---- the receipt is published the morning after the record it binds: an
  // update check that finds the record unchanged reads it again, past the cache
  {
    let body = JSON.stringify(production), hits = 0;
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/thin.json', FRESH, 1280, { reducedMotion: 'reduce', lens: 'all', hash: '#/method',
      beforeLoad: async (pg) => {
        // the route answers every request itself, which the browser's HTTP cache never sees, so
        // the cache mode is read off the page's own fetch call instead
        await pg.addInitScript(() => {
          const fetch = window.fetch; window.__recoveryCache = [];
          window.fetch = function (input, init) { if (/source-recovery\.json/.test(String(input))) window.__recoveryCache.push(init && init.cache); return fetch.apply(this, arguments); };
        });
        await pg.route('**/source-recovery.json', (route) => { hits++; route.fulfill({ contentType: 'application/json', body, headers: { 'Cache-Control': 'max-age=600' } }); });
      } });
    try {
      eq('evening: another publication\'s receipt', (await recoveryLine(page)).state, 'unbound');
      body = JSON.stringify(recovered);
      await page.evaluate(() => window.SCStock.checkUpdates());
      await page.waitForFunction(() => document.querySelector('#run-meta li[data-source-recovery]').getAttribute('data-source-recovery') === 'recovered', null, { timeout: 15000 }).catch(() => {});
      const got = await recoveryLine(page);
      eq('morning: the unchanged record\'s check reads the new receipt', [got.state, got.text], ['recovered', PREFIX + recovered.sentence]);
      eq('morning: two reads of the receipt, the second past the cache', hits, 2);
      eq('each read asks past the HTTP cache', await page.evaluate(() => window.__recoveryCache), ['no-store', 'no-store']);
      await page.evaluate(() => { location.hash = '#/record'; }); await page.waitForTimeout(150);
      await page.evaluate(() => window.SCStock.checkUpdates()); await page.waitForTimeout(400);
      eq('an unchanged check away from Method reads nothing', hits, 2);
      eq('refresh page errors', [...errors], []);
    } finally { await context.close(); }
  }
}
