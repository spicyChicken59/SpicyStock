/* The candidate funnel on the page is the record's own block, printed: the
   run gave every discovered candidate one terminal stage and wrote the counts,
   the labels and the sentence; the scan disclosure prints the table and the
   sentence, each matrix row says where its name stopped, and a record made
   under older rules says the funnel was not archived. Nothing here is added
   up by the browser, and the checks below hold every printed number to the
   block it came from -- including a block whose numbers are NOT the page's
   own counts, so a page that counted for itself would be caught. Lane B:
   this suite writes no scratch record and reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const FIXTURES = path.resolve('tests/fixtures/page');

const cellNumber = (s) => (s.trim() === '' ? null : Number(s.replace(/,/g, '')));
const nonzero = (stages) => Object.keys(stages).filter((k) => stages[k] > 0);

async function tableOf(page) {
  return page.locator('#scan-body [data-funnel-table] tbody tr').evaluateAll((rows) => rows.map((tr) => ({
    stage: tr.getAttribute('data-funnel-row'),
    label: tr.querySelector('th').textContent,
    cells: Array.from(tr.querySelectorAll('td')).map((td) => td.textContent),
    reaction: tr.children[1] ? tr.children[1].textContent : '', anticipation: tr.children[2] ? tr.children[2].textContent : '',
  })));
}

async function openScan(page, expectRows) {
  await page.locator('#scan-summary').click();
  if (expectRows) await page.waitForFunction((n) => document.querySelectorAll('#scan-table tbody tr').length === n, expectRows);
}

async function capture(page, shotsDir, name) {
  if (!shotsDir) return;
  await mkdir(shotsDir, { recursive: true });
  // the element's own capture: it scrolls the section into view and takes the
  // whole of it, so a phone's table is in the picture and not under the fold
  await page.locator('#scan-body [data-funnel]').screenshot({ path: path.join(shotsDir, `funnel-${name}.png`) });
}

// a record served from memory in place of a fixture, so a shape the generator
// never writes can be put in front of the page
function routed(name, record) {
  const body = JSON.stringify(record);
  return { url: `/funnel-${name}.json`, beforeLoad: (p) => p.route(`**/funnel-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) };
}

export async function checkFunnel({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- funnel: where the candidates stopped, printed from the record');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const red = JSON.parse(await readFile(path.join(FIXTURES, 'red.json'), 'utf8'));
  const empty = JSON.parse(await readFile(path.join(FIXTURES, 'empty.json'), 'utf8'));
  const clone = (d) => JSON.parse(JSON.stringify(d));

  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [390, 'dark'], [320, 'dark']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { height: width < 400 ? 844 : 900, theme, reducedMotion: 'reduce', lens: 'all' });
    try {
      const fu = full.funnel, where = `${width} ${theme}`;
      eq(`${where}: the scan body carries the funnel as present`, await page.locator('#scan-body [data-funnel]').getAttribute('data-funnel'), 'present');
      eq(`${where}: the sentence is the record's own`, (await page.locator('#scan-body [data-funnel-sentence]').textContent()), fu.sentence);
      check(`${where}: the scan lede introduces the funnel before the matrix`, (await page.locator('#scan-lede').textContent()).startsWith('Where the candidates stopped, counted by the run; then every burst against its'));
      const rows = await tableOf(page);
      const stageRows = rows.filter((r) => !['discovered', 'potentially_usable', 'none'].includes(r.stage));
      const expected = Array.from(new Set([...nonzero(fu.reaction.stages), ...nonzero(fu.anticipation.stages)]));
      eq(`${where}: one row per stage a candidate stopped at, in gate order`, stageRows.map((r) => r.stage), expected);
      for (const r of stageRows) {
        eq(`${where}: ${r.stage} wears the record's label`, r.label, fu.labels[r.stage]);
        eq(`${where}: ${r.stage} reaction count is the block's`, cellNumber(r.reaction), r.stage in fu.reaction.stages ? fu.reaction.stages[r.stage] : null);
        eq(`${where}: ${r.stage} anticipation count is the block's`, cellNumber(r.anticipation), r.stage in fu.anticipation.stages ? fu.anticipation.stages[r.stage] : null);
      }
      const head = rows.find((r) => r.stage === 'discovered'), usable = rows.find((r) => r.stage === 'potentially_usable');
      eq(`${where}: discovered and listed are the block's`, [cellNumber(head.reaction), cellNumber(head.anticipation)], [fu.reaction.discovered, fu.anticipation.listed]);
      eq(`${where}: potentially usable is the block's, and not a figure for anticipation`, [cellNumber(usable.reaction), usable.anticipation], [fu.reaction.potentially_usable, '']);
      check(`${where}: a stage that is not a family's prints an empty cell, never an unreported mark`, rows.every((r) => !r.cells.some((c) => c.includes('—'))));
      const reactionSum = stageRows.reduce((n, r) => n + (cellNumber(r.reaction) || 0), 0);
      eq(`${where}: the printed reaction stages sum to the discovered count`, reactionSum, fu.reaction.discovered);
      // the table's own accessibility: a caption, column headers, a row header per stage
      check(`${where}: the table carries its caption`, (await page.locator('#scan-body [data-funnel-table] caption').textContent()).startsWith('The candidate funnel: where the discovered reaction candidates and the listed anticipation setups ended, one terminal stage each'));
      eq(`${where}: the column headers`, await page.locator('#scan-body [data-funnel-table] thead th').allTextContents(), ['stage', 'bursts', 'setups']);
      eq(`${where}: every body row is headed by its stage`, await page.locator('#scan-body [data-funnel-table] tbody th[scope="row"]').count(), rows.length);
      // every stock in the matrix says where it stopped, except the tickets
      await openScan(page, full.bursts.length);
      check(`${where}: the funnel precedes the matrix it is counted from`, await page.evaluate(() => {
        const f = document.querySelector('#scan-body [data-funnel]'), m = document.querySelector('#scan [data-sc-matrix-nav]');
        return !!f && !!m && !!(f.compareDocumentPosition(m) & Node.DOCUMENT_POSITION_FOLLOWING);
      }));
      const notes = await page.locator('#scan-table tbody tr').evaluateAll((trs) => trs.map((tr) => [tr.dataset.ticker, tr.querySelector('.ss-grade-note').textContent]));
      for (const [ticker, note] of notes) {
        const row = fu.reaction.rows.find((r) => r.ticker === ticker);
        if (row.stage === 'ticket') check(`${where}: ${ticker} the ticket carries no stop`, !note.includes('stopped at:'), note);
        else check(`${where}: ${ticker} says where it stopped`, note.includes('stopped at: ' + fu.labels[row.stage]), note);
      }
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      // the table itself fits its scroll box, and the stage column keeps a readable share of it
      const fit = await page.locator('#scan-body [data-funnel] .sc-table-scroll').evaluate((box) => {
        const th = box.querySelector('tbody th'), table = box.querySelector('table');
        return { overflow: box.scrollWidth - box.clientWidth, stage: th.getBoundingClientRect().width, table: table.getBoundingClientRect().width };
      });
      check(`${where}: the funnel table fits its box without a hidden scroll`, fit.overflow <= 0, JSON.stringify(fit));
      check(`${where}: the stage column keeps at least half the table`, fit.stage >= fit.table / 2, JSON.stringify(fit));
      await capture(page, shotsDir, `${width}-${theme}`);
      eq(`${where}: no page errors`, errors.slice(), []);
    } finally { await context.close(); }
  }

  // a red night: everything stopped at the market, both families
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/red.json', NOW, 1280, { reducedMotion: 'reduce', lens: 'all' });
    try {
      await openScan(page, red.bursts.length);
      const rows = await tableOf(page);
      eq('red: the one stage row is the market gate', rows.filter((r) => !['discovered', 'potentially_usable'].includes(r.stage)).map((r) => [r.stage, cellNumber(r.reaction), cellNumber(r.anticipation)]),
        [['market', red.funnel.reaction.stages.market, red.funnel.anticipation.stages.market]]);
      check('red: every matrix row says it stopped at the market', (await page.locator('#scan-table tbody tr .ss-grade-note').allTextContents()).every((t) => t.includes('stopped at: ' + red.funnel.labels.market)));
      eq('red: no page errors', errors.slice(), []);
    } finally { await context.close(); }
  }

  // an empty night: a present block with nothing to count says so, in words and not a figure
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/empty.json', NOW, 1280, { reducedMotion: 'reduce' });
    try {
      eq('empty: the funnel is present', await page.locator('#scan-body [data-funnel]').getAttribute('data-funnel'), 'present');
      eq('empty: the sentence is the record\'s own', await page.locator('#scan-body [data-funnel-sentence]').textContent(), empty.funnel.sentence);
      const none = (await tableOf(page)).filter((r) => r.stage === 'none');
      eq('empty: one row says no candidate reached a gate', none.length, 1);
      eq('empty: that row counts nothing of its own', none[0].cells, ['none counted']);
      eq('empty: no page errors', errors.slice(), []);
    } finally { await context.close(); }
  }

  // the numbers are the block's and not the page's: a block whose counts do not
  // match the record's own lists is printed as written
  {
    const record = clone(full);
    record.funnel.reaction.discovered = 12345; record.funnel.anticipation.listed = 6789;
    record.funnel.reaction.potentially_usable = 1234;
    for (const k of Object.keys(record.funnel.reaction.stages)) record.funnel.reaction.stages[k] = 0;
    const { url, beforeLoad } = routed('block-not-page', record);
    for (const width of [1280, 320]) {
      const { page, context, errors } = await open(browser, base, url, NOW, width, { height: width < 400 ? 844 : 900, reducedMotion: 'reduce', lens: 'all', beforeLoad });
      try {
        const rows = await tableOf(page);
        const head = rows.find((r) => r.stage === 'discovered'), usable = rows.find((r) => r.stage === 'potentially_usable');
        eq(`${width} block-not-page: discovered and listed are printed from the block, not counted from the lists`, [cellNumber(head.reaction), cellNumber(head.anticipation)], [12345, 6789]);
        eq(`${width} block-not-page: potentially usable likewise`, cellNumber(usable.reaction), 1234);
        const none = rows.find((r) => r.stage === 'none');
        check(`${width} block-not-page: the reaction stages at zero leave no reaction row, and the row that says so carries no figure`, !rows.some((r) => r.stage in full.funnel.reaction.stages && !(r.stage in full.funnel.anticipation.stages)) && (!none || none.cells.every((c) => !/\d/.test(c))));
        const fit = await page.locator('#scan-body [data-funnel] .sc-table-scroll').evaluate((box) => box.scrollWidth - box.clientWidth);
        check(`${width} block-not-page: five-digit counts still fit the box`, fit <= 0, String(fit));
        eq(`${width} block-not-page: no page errors`, errors.slice(), []);
      } finally { await context.close(); }
    }
  }

  // a ticker spelled like an Object property, with no funnel row of its own,
  // resolves to no stage: the matrix renders and says nothing of it
  {
    const record = clone(full);
    const victim = record.funnel.reaction.rows.find((r) => r.stage !== 'ticket').ticker;
    const burst = record.bursts.find((b) => b.ticker === victim);
    burst.ticker = 'constructor';
    record.funnel.reaction.rows = record.funnel.reaction.rows.filter((r) => r.ticker !== victim);
    const { url, beforeLoad } = routed('proto-ticker', record);
    const { page, context, errors } = await open(browser, base, url, NOW, 1280, { reducedMotion: 'reduce', lens: 'all', beforeLoad, hash: '#scan' });
    try {
      check('proto-ticker: the page rendered through the scan deep link', !['error', 'failed', null].includes(await page.evaluate(() => document.documentElement.getAttribute('data-ss-rendered'))));
      await page.waitForFunction((n) => document.querySelectorAll('#scan-table tbody tr').length === n, record.bursts.length);
      const note = await page.locator('#scan-table tbody tr[data-ticker="constructor"] .ss-grade-note').textContent();
      check('proto-ticker: the name without a row claims no stage', !note.includes('stopped at:'), note);
      eq('proto-ticker: no page errors', errors.slice(), []);
    } finally { await context.close(); }
  }

  // a record from before the block, or one whose block cannot be read, says the
  // funnel was not archived: every clause of the shape check, one at a time
  for (const [name, mutate] of [
    ['older-rules', (d) => { delete d.funnel; delete d.rules.funnel; }],
    ['half-written', (d) => { d.funnel = { version: 1, reaction: { discovered: 6 } }; }],
    ['no-labels', (d) => { delete d.funnel.labels; }],
    ['labels-array', (d) => { d.funnel.labels = ['market']; }],
    ['no-sentence', (d) => { delete d.funnel.sentence; }],
    ['sentence-blank', (d) => { d.funnel.sentence = '   '; }],
    ['no-discovered', (d) => { delete d.funnel.reaction.discovered; }],
    ['discovered-fraction', (d) => { d.funnel.reaction.discovered = 6.5; }],
    ['no-listed', (d) => { delete d.funnel.anticipation.listed; }],
    ['listed-object', (d) => { d.funnel.anticipation.listed = { n: 1 }; }],
    ['no-reaction-stages', (d) => { delete d.funnel.reaction.stages; }],
    ['no-anticipation-stages', (d) => { delete d.funnel.anticipation.stages; }],
    ['stages-array', (d) => { d.funnel.reaction.stages = [3, 2]; }],
    ['count-string', (d) => { d.funnel.reaction.stages.market = '2'; }],
    ['count-negative', (d) => { d.funnel.anticipation.stages.market = -1; }],
    ['rows-string', (d) => { d.funnel.reaction.rows = 'rows'; }],
    ['rows-missing', (d) => { delete d.funnel.reaction.rows; }],
    ['stage-number', (d) => { d.funnel.reaction.rows[1].stage = 5; }],
    ['row-null', (d) => { d.funnel.reaction.rows[0] = null; }],
  ]) {
    const record = clone(full); mutate(record);
    const { url, beforeLoad } = routed(name, record);
    // the scan deep link renders the matrix inside the first render, where a
    // crash would take the whole page down rather than one disclosure
    const { page, context, errors } = await open(browser, base, url, NOW, 1280, { reducedMotion: 'reduce', lens: 'all', beforeLoad, hash: name === 'stage-number' ? '#scan' : '' });
    try {
      // read without waiting out a locator: a page that failed to render the
      // section at all is a named failure here, not a timeout
      const marker = page.locator('#scan-body [data-funnel]');
      eq(`${name}: the funnel is absent`, (await marker.count()) ? await marker.getAttribute('data-funnel') : 'no section rendered', 'absent');
      const note = page.locator('#scan-body [data-funnel-note]');
      check(`${name}: the note says it was not archived`, (await note.count()) ? (await note.textContent()).includes('not archived') : false);
      const rendered = await page.evaluate(() => document.documentElement.getAttribute('data-ss-rendered'));
      check(`${name}: the rest of the page rendered`, !['error', 'failed', null].includes(rendered), rendered);
      eq(`${name}: no table and no sentence are invented`, await page.locator('#scan-body [data-funnel-table], #scan-body [data-funnel-sentence]').count(), 0);
      check(`${name}: the scan lede does not promise a funnel`, (await page.locator('#scan-lede').textContent()).startsWith('Every burst against its'));
      if (name !== 'stage-number') await openScan(page, full.bursts.length);
      else await page.waitForFunction((n) => document.querySelectorAll('#scan-table tbody tr').length === n, full.bursts.length);
      check(`${name}: no matrix row claims a stage`, (await page.locator('#scan-table tbody tr .ss-grade-note').allTextContents()).every((t) => !t.includes('stopped at:')));
      eq(`${name}: no page errors`, errors.slice(), []);
    } finally { await context.close(); }
  }
}
