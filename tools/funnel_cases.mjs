/* The candidate funnel on the page is the record's own block, printed: the
   run gave every discovered candidate one terminal stage and wrote the counts,
   the labels and the sentence; the scan disclosure prints the table and the
   sentence, each matrix row says where its name stopped, and a record made
   under older rules says the funnel was not archived. Nothing here is added
   up by the browser, and the checks below hold every printed number to the
   block it came from. Lane B: this suite writes no scratch record and reads
   no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const FIXTURES = path.resolve('tests/fixtures/page');

const cellNumber = (s) => (s.trim() === '—' ? null : Number(s.replace(/,/g, '')));
const nonzero = (stages) => Object.keys(stages).filter((k) => stages[k] > 0);

async function tableOf(page) {
  return page.locator('#scan-body [data-funnel-table] tbody tr').evaluateAll((rows) => rows.map((tr) => ({
    stage: tr.getAttribute('data-funnel-row'),
    label: tr.querySelector('th').textContent,
    reaction: tr.children[1].textContent, anticipation: tr.children[2].textContent,
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

export async function checkFunnel({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- funnel: where the candidates stopped, printed from the record');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const red = JSON.parse(await readFile(path.join(FIXTURES, 'red.json'), 'utf8'));
  const empty = JSON.parse(await readFile(path.join(FIXTURES, 'empty.json'), 'utf8'));

  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [390, 'dark']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { height: width === 390 ? 844 : 900, theme, reducedMotion: 'reduce', lens: 'all' });
    try {
      const fu = full.funnel, where = `${width} ${theme}`;
      eq(`${where}: the scan body carries the funnel as present`, await page.locator('#scan-body [data-funnel]').getAttribute('data-funnel'), 'present');
      eq(`${where}: the sentence is the record's own`, (await page.locator('#scan-body [data-funnel-sentence]').textContent()), fu.sentence);
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
      eq(`${where}: potentially usable is the block's, and not a figure for anticipation`, [cellNumber(usable.reaction), cellNumber(usable.anticipation)], [fu.reaction.potentially_usable, null]);
      const reactionSum = stageRows.reduce((n, r) => n + (cellNumber(r.reaction) || 0), 0);
      eq(`${where}: the printed reaction stages sum to the discovered count`, reactionSum, fu.reaction.discovered);
      // every stock in the matrix says where it stopped, except the tickets
      await openScan(page, full.bursts.length);
      const notes = await page.locator('#scan-table tbody tr').evaluateAll((trs) => trs.map((tr) => [tr.dataset.ticker, tr.querySelector('.ss-grade-note').textContent]));
      for (const [ticker, note] of notes) {
        const row = fu.reaction.rows.find((r) => r.ticker === ticker);
        if (row.stage === 'ticket') check(`${where}: ${ticker} the ticket carries no stop`, !note.includes('stopped at:'), note);
        else check(`${where}: ${ticker} says where it stopped`, note.includes('stopped at: ' + fu.labels[row.stage]), note);
      }
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
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

  // an empty night: a present block with nothing to count says so
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/empty.json', NOW, 1280, { reducedMotion: 'reduce' });
    try {
      eq('empty: the funnel is present', await page.locator('#scan-body [data-funnel]').getAttribute('data-funnel'), 'present');
      eq('empty: the sentence is the record\'s own', await page.locator('#scan-body [data-funnel-sentence]').textContent(), empty.funnel.sentence);
      eq('empty: one row says no candidate reached a gate', (await tableOf(page)).filter((r) => r.stage === 'none').length, 1);
      eq('empty: no page errors', errors.slice(), []);
    } finally { await context.close(); }
  }

  // a record from before the block, or one whose block is missing, says the funnel was not archived
  for (const [name, mutate] of [
    ['older-rules', (d) => { delete d.funnel; delete d.rules.funnel; }],
    ['half-written', (d) => { d.funnel = { version: 1, reaction: { discovered: 6 } }; }],
    // the shapes the drawing indexes into, each missing on its own: a block with
    // its stages but no labels, no sentence, no discovered count
    ['no-labels', (d) => { delete d.funnel.labels; }],
    ['no-sentence', (d) => { delete d.funnel.sentence; }],
    ['no-discovered', (d) => { delete d.funnel.reaction.discovered; }],
  ]) {
    const record = JSON.parse(JSON.stringify(full)); mutate(record);
    const body = JSON.stringify(record);
    const { page, context, errors } = await open(browser, base, `/funnel-${name}.json`, NOW, 1280, { reducedMotion: 'reduce', lens: 'all',
      beforeLoad: (p) => p.route(`**/funnel-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) });
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
      await openScan(page, full.bursts.length);
      check(`${name}: no matrix row claims a stage`, (await page.locator('#scan-table tbody tr .ss-grade-note').allTextContents()).every((t) => !t.includes('stopped at:')));
      eq(`${name}: no page errors`, errors.slice(), []);
    } finally { await context.close(); }
  }
}
