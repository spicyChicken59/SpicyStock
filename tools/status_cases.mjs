/* UI controls over pipeline-generated fixtures: recorded tickets span both
   stages, while an Actions result never establishes publication freshness. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const PREOPEN = '2026-09-11T13:20:00Z';
const OPEN = '2026-09-11T13:40:00Z';
const ENDED = '2026-09-11T14:00:00Z';
const STALE = '2026-09-16T13:40:00Z';

export async function checkMorningStatus({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- morning status: both ticket families and workflow-only outcomes');
  const fixture = async name => {
    const record = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page', name + '.json')));
    delete record.fixture; // Explicit synthetic controls for publication-state wording.
    return record;
  };
  const anticipation = await fixture('notrade'), burstOnly = await fixture('full');
  const weekend = await fixture('next'), holiday = await fixture('closed');
  const mixed = structuredClone(burstOnly);
  mixed.watchlist.top = structuredClone(anticipation.watchlist.top);
  // These are UI controls, not newly generated or verified strategy records.
  const withheld = structuredClone(anticipation);
  for (const row of withheld.watchlist.top) {
    row.plan.eligible = false; row.plan.action = 'refused'; row.plan.order_json = null; row.plan.order_line = null;
  }
  const red = structuredClone(anticipation); red.breadth.regime.verdict = 'red';
  const unknown = structuredClone(anticipation); delete unknown.run.timing;
  for (const width of [1280, 390]) {
    let workflow = { id: 22, status: 'completed', conclusion: 'success', updated_at: '2026-09-16T05:10:00Z',
      html_url: 'https://github.com/spicyChicken59/SpicyStock/actions/runs/22' };
    const { page, context, errors } = await open(browser, base, '/status-control.json', PREOPEN, width, {
      reducedMotion: 'reduce', beforeLoad: async page => {
        await page.route('**/status-control.json', route => route.fulfill({ json: anticipation }));
        await page.route('https://api.github.com/**', route => route.fulfill({ json: { workflow_runs: [workflow] } }));
      }
    });
    const render = (record, now) => page.evaluate(({ record, now }) => SCStock.render(record, new Date(now)), { record, now });
    const headline = () => page.locator('#next-h3').textContent();
    const body = () => page.locator('#next-p').textContent();
    try {
      // Literal expectations use retained fixture plans, not the model
      // selector being fixed: one coil, a mixed UI control, one burst.
      for (const [name, record, count, family] of [
        ['anticipation only', anticipation, 1, '0 burst · 1 setting up'],
        ['mixed stages', mixed, 2, '1 burst · 1 setting up'],
        ['withheld coil beside burst', burstOnly, 1, '1 burst · 0 setting up']
      ]) {
        const original = JSON.stringify(record);
        await render(record, PREOPEN);
        eq(`${width} ${name}: both stages agree before open`, await headline(), `Review ${count} conditional ticket${count === 1 ? '' : 's'} for Fri 11 Sep.`);
        eq(`${width} ${name}: morning family counts`, await page.locator('[data-morning="plans"]').textContent(), family);
        await render(record, OPEN);
        eq(`${width} ${name}: window stays conditional`, await headline(), 'The entry window for Fri 11 Sep is in progress.');
        check(`${width} ${name}: open-window count`, (await body()).includes(`Review the ${count} conditional ticket`));
        await render(record, ENDED);
        check(`${width} ${name}: historical ticket count survives cutoff`, (await body()).includes(`The ${count} ticket`) && !(await body()).includes('Nothing new was offered'));
        eq(`${width} ${name}: clock never changes publication`, await page.evaluate(() => JSON.stringify(SCStock.data)), original);
      }
      for (const [name, record, now, expected] of [
        ['withheld anticipation', withheld, PREOPEN, /^(Nothing new|No new entry|No new burst ticket)/],
        ['stale publication', anticipation, STALE, /^Do not place these orders/],
        ['red market', red, OPEN, /^No new longs/],
        ['unknown timing', unknown, PREOPEN, /^Entry timing unavailable/]
      ]) {
        await render(record, now);
        check(`${width} ${name}: refusal keeps precedence`, expected.test(await headline()), await headline());
        check(`${width} ${name}: no new-ticket instruction`, !/^Review \d+ conditional ticket/.test(await headline()));
      }
      await render(withheld, OPEN);
      check(`${width} zero tickets: explanation covers both stages`, !(await body()).includes('No burst qualified'));
      for (const [name, record, now, measured, closedDay, nextDay] of [
        ['weekend after an open Friday', weekend, '2026-09-12T14:00:00Z', 'Fri 11 Sep', 'Sat 12 Sep', 'Mon 14 Sep'],
        ['holiday after an open Friday', holiday, '2026-09-07T14:00:00Z', 'Fri 4 Sep', 'Mon 7 Sep', 'Tue 8 Sep']
      ]) {
        const original = JSON.stringify(record);
        await render(record, now);
        eq(`${width} ${name}: measured session was open`, record.run.session_state, 'open');
        eq(`${width} ${name}: viewing date is closed`, await page.evaluate(() => SCStock.state.state), 'closed');
        check(`${width} ${name}: next step names the actual closed date`, (await body()).includes('market was closed on ' + closedDay), await body());
        check(`${width} ${name}: next session comes from the recorded calendar`, (await body()).includes('next applicable session is ' + nextDay), await body());
        check(`${width} ${name}: measured Friday is never called sessionless`, !(await body()).includes('closed on ' + measured) && !(await body()).includes('had no session'), await body());
        eq(`${width} ${name}: calendar wording changes no published plans`, await page.evaluate(() => JSON.stringify(SCStock.data)), original);
        if (shotsDir) {
          await mkdir(shotsDir, { recursive: true });
          await page.locator('#next').screenshot({ path: path.join(shotsDir, `status-${name.startsWith('weekend') ? 'weekend' : 'holiday'}-${width}.png`) });
        }
      }
      for (const [status, conclusion, expected] of [
        ['completed', 'success', 'completed successfully'],
        ['completed', 'cancelled', 'cancelled'],
        ['completed', 'skipped', 'skipped'],
        ['completed', 'failure', 'failure'],
        ['completed', null, 'completed (outcome unknown)'],
        ['in_progress', null, 'in progress']
      ]) {
        workflow = { ...workflow, status, conclusion, run_started_at: '2026-09-16T05:00:00Z' };
        await render(anticipation, STALE);
        await page.waitForFunction(() => { const n = document.getElementById('runlog'); return n && !n.hidden; });
        const log = await page.locator('#runlog').textContent();
        check(`${width} ${status}/${conclusion}: workflow outcome stays distinct`, log.includes('Latest evening workflow: ' + expected), log);
        check(`${width} ${status}/${conclusion}: a workflow does not prove publication`, log.includes('may skip publication') && !log.includes('tonight’s run'), log);
        check(`${width} ${status}/${conclusion}: absolute exchange date is present`, log.includes('Wed 16 Sep'), log);
        eq(`${width} ${status}/${conclusion}: stale record remains refused`, await headline(), 'Do not place these orders.');
      }
      await render(anticipation, PREOPEN);
      check(`${width} next-action fits viewport`, await page.locator('#next').evaluate(n => n.scrollWidth <= n.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#next').screenshot({ path: path.join(shotsDir, `status-anticipation-${width}.png`) });
      }
      eq(`${width} status browser errors`, [...errors], []);
    } finally { await context.close(); }
  }
}
