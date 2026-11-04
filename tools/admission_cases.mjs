/* The discovery admission on the page (src/admission.py, 4 Nov 2026): a name
   the 4% scan found is admitted to the trade band and the chart reads; a name
   the dollar scan alone found is admitted only on a range-expansion,
   higher-volume day. The page prints what the record wrote and decides
   nothing: the A-quality lens holds the admitted A and A+ alone, a stopped
   name wears the chip "dollar scan alone" and prints the record's own reason,
   the Method view prints the night's admission sentence and the rule the
   record archived, the funnel's route stage is a row, and the Morning desk's
   reconciliation reads the version-2 selection under its own blocker. A
   record from before the rule (the exact retained 9 Oct 2026 publication)
   reads every A as admitted and is reconciled under version 1. Lane B: this
   suite writes no scratch record and reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const FIXTURES = path.resolve('tests/fixtures/page');
//: the exact retained 9 October 2026 publication: no admission rule, selection version 1
const RETAINED = path.resolve('tests/fixtures/stop-research/current-publication.json.gz');
const RETAINED_NOW = '2026-10-10T12:01:00Z';
const STOPPED_WORDS = 'dollar scan alone, without a range-expansion, higher-volume day';

// a record served from memory in place of a fixture, so a shape the generator
// never writes can be put in front of the page
function routed(name, record) {
  const body = JSON.stringify(record);
  return { url: `/admission-${name}.json`, beforeLoad: (p) => p.route(`**/admission-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) };
}

const cardTickers = (page) => page.locator('#pick-list .ss-pick').evaluateAll((e) => e.map((x) => x.dataset.ticker));
const lensCounts = (page) => page.locator('#lens .sc-tab[data-lens]').evaluateAll((e) => Object.fromEntries(e.map((x) => [x.dataset.lens, +x.dataset.count])));
async function setLens(page, lens) {
  await page.click(`#lens .sc-tab[data-lens="${lens}"]`);
  await page.waitForFunction((l) => document.querySelector(`#lens .sc-tab[data-lens="${l}"]`).getAttribute('aria-pressed') === 'true', lens);
}
const methodLines = (page) => page.locator('#run-meta li').allTextContents();
// the archived counts still print their note; what a contradicted row withholds is the reconciled detail
const unreconciled = (f) => !!f && f.detail === null;
const facts = (page) => page.evaluate(() => { const f = SCStock.reviewSelectionFacts(SCStock.data); return f ? { note: f.note, detail: f.detail ? { unreviewedQuality: f.detail.unreviewedQuality, unreviewedWord: f.detail.unreviewedWord, coverage: f.detail.coverage } : null } : null; });

export async function checkAdmission({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- admission: which discovered candidates the trade band and the reads could consider');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const clone = (d) => JSON.parse(JSON.stringify(d));
  const msft = full.bursts.find((b) => b.ticker === 'MSFT');
  const admittedA = full.bursts.filter((b) => ['A+', 'A'].includes(b.grade) && b.admission.admitted).map((b) => b.ticker);
  const allA = full.bursts.filter((b) => ['A+', 'A'].includes(b.grade)).map((b) => b.ticker);
  check('the fixture carries a dollar-only A the admission stopped', msft && msft.scan === 'dollar' && msft.grade === 'A' && msft.admission.admitted === false && !msft.plan && msft.claude === null, JSON.stringify(msft && msft.admission));
  check('and admitted names it does not', admittedA.length === allA.length - 1 && !admittedA.includes('MSFT'), JSON.stringify({ admittedA, allA }));

  for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { theme, reducedMotion: 'reduce' });
    try {
      const where = `${width} ${theme}`;
      // the lens: admitted A and A+ alone, the count on the tab the same list's
      eq(`${where}: the first visit opens on the A-quality lens`, await page.locator('#lens .sc-tab[data-lens][aria-pressed="true"]').getAttribute('data-lens'), 'a');
      eq(`${where}: the A-quality lens holds the admitted A and A+ alone`, await cardTickers(page), admittedA);
      eq(`${where}: the tab wears that count beside every burst`, [(await lensCounts(page)).a, (await lensCounts(page)).all], [admittedA.length, full.bursts.length]);
      eq(`${where}: the heading keeps the stage total beside the subset`, await page.locator('#picks-h2').innerText(), `bursts · ${admittedA.length} of ${full.bursts.length}`);
      check(`${where}: the model reads the row's admission`, await page.evaluate(() => { const c = SCStock.model.stages.bursts.find((x) => x.ticker === 'MSFT'), a = SCStock.model.stages.bursts.find((x) => x.ticker === 'AAPL'); return c.admitted === false && c.status === 'route' && a.admitted === true; }));
      await setLens(page, 'all');
      eq(`${where}: every burst shows under All, the stopped name among them`, (await cardTickers(page)).includes('MSFT'), true);
      eq(`${where}: the stopped name wears its own chip`, await page.locator('#pick-list .ss-pick[data-ticker="MSFT"]').evaluate((b) => [b.dataset.status, Array.from(b.querySelectorAll('.sc-chip')).map((c) => c.textContent).pop()]), ['route', 'dollar scan alone']);
      // the stock: the record's own reason, no order, the admission in the discovery sentence
      await page.evaluate(() => { location.hash = '#/explore/bursts/MSFT'; });
      await page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'bursts:MSFT');
      eq(`${where}: the detail is MSFT`, await page.locator('#detail-h2').innerText(), 'MSFT');
      const why = await page.locator('#detail [data-item="why"] p').allTextContents();
      check(`${where}: the discovery sentence carries the admission in the record's words`, why.some((p) => p.includes('Admission: ' + msft.admission.reason.charAt(0).toUpperCase() + msft.admission.reason.slice(1) + '.')), JSON.stringify(why));
      const need = await page.locator('#detail [data-item="need"] p').allTextContents();
      check(`${where}: what would need to happen names the stop, not an entry`, need.some((p) => p.includes('This record offers no entry: ' + STOPPED_WORDS)), JSON.stringify(need));
      eq(`${where}: no order control for a name the admission stopped`, await page.locator('#detail [data-order], #detail [data-copy]').count(), 0);
      check(`${where}: the action area says there is no SpicyStock entry and why`, (await page.locator('#detail').innerText()).includes('No SpicyStock entry for this setup'), 'action area');
      eq(`${where}: no page errors so far`, errors, []);
      // the Method view: the night's sentence and the archived rule, in the record's words
      await page.evaluate(() => SCStock.navigate('#/method'));
      const lines = await methodLines(page);
      check(`${where}: Method prints the night's admission sentence verbatim`, lines.includes(full.run.admission.sentence), JSON.stringify(lines.filter((l) => l.startsWith('Admission'))));
      check(`${where}: Method states the rule the record archived`, lines.some((l) => l.startsWith('Admission rule, as this record archived it: a name the 4% scan discovered is admitted; a name the dollar scan alone discovered is admitted only when its burst day passes the checklist’s RE and VOL checks')), JSON.stringify(lines.filter((l) => l.startsWith('Admission rule'))));
      check(`${where}: the review-selection line is reconciled under version 2`, lines.some((l) => l.startsWith('Before chart review,')));
      const f = await facts(page);
      const unreviewedAdmitted = full.bursts.filter((b) => ['A+', 'A'].includes(b.grade) && b.admission.admitted && b.reader_coverage !== 'accepted').length;
      check(`${where}: the Morning desk reconciles the version-2 selection and counts admitted A-band names only`, !!f && !!f.detail && f.detail.unreviewedWord === 'admitted mechanical A+/A' && f.detail.unreviewedQuality === unreviewedAdmitted && f.detail.coverage.includes(unreviewedAdmitted + ' admitted mechanical A+/A lack accepted review'), JSON.stringify([f, unreviewedAdmitted]));
      // the funnel: a route row with the record's label, the usable row naming the admission
      await page.evaluate(() => SCStock.navigate('#/explore/bursts/MSFT'));
      await page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'bursts:MSFT');
      await page.locator('#scan-summary').click();
      await page.waitForFunction((n) => document.querySelectorAll('#scan-table tbody tr').length === n, full.bursts.length);
      const route = page.locator('#scan-body [data-funnel-table] tbody tr[data-funnel-row="route"]');
      eq(`${where}: the funnel prints the route stage with the record's label and count`, (await route.count()) ? await route.evaluate((tr) => [tr.querySelector('th').textContent, tr.children[1].textContent]) : null, [STOPPED_WORDS, String(full.funnel.reaction.stages.route)]);
      check(`${where}: the usable row says the admission is among the first gates`, (await page.locator('#scan-body [data-funnel-table] tbody tr[data-funnel-row="potentially_usable"] th').innerText()).endsWith(', discovery admitted'));
      check(`${where}: the matrix row says where MSFT stopped`, (await page.locator('#scan-table tbody tr[data-ticker="MSFT"] .ss-grade-note').innerText()).includes('stopped at: ' + STOPPED_WORDS));
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.evaluate(() => SCStock.navigate('#/explore/bursts/MSFT'));
        await page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'bursts:MSFT');
        await page.locator('#detail').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(shotsDir, `admission-stopped-${width}-${theme}.png`), fullPage: false });
      }
      eq(`${where}: no page errors`, errors, []);
    } finally { await context.close(); }
  }

  // a record from before the rule: every A admitted, no admission line beyond the dated note, version-1 reconciliation
  {
    const retained = JSON.parse(gunzipSync(await readFile(RETAINED)).toString('utf8'));
    check('the retained 9 Oct publication predates the rule', !('admission' in retained.rules) && retained.bursts.every((b) => !('admission' in b)) && retained.rules.review_selection.version === 1);
    const r = routed('retained', retained);
    const { page, context, errors } = await open(browser, base, r.url, RETAINED_NOW, 1280, { beforeLoad: r.beforeLoad, reducedMotion: 'reduce' });
    try {
      const everyA = retained.bursts.filter((b) => ['A+', 'A'].includes(b.grade)).map((b) => b.ticker);
      eq('a record from before the rule shows every A and A+ under the A-quality lens', (await lensCounts(page)).a, everyA.length);
      check('and none of its cards wears the stopped chip', (await page.locator('#pick-list .ss-pick[data-status="route"]').count()) === 0);
      await page.evaluate(() => SCStock.navigate('#/method'));
      const lines = await methodLines(page);
      check('Method says the record predates the admission rule', lines.includes('Admission rule: this record predates the discovery admission; every graded name could be planned and read, the dollar scan’s days included.'), JSON.stringify(lines.filter((l) => l.startsWith('Admission'))));
      check('and prints no admission sentence of its own', !lines.some((l) => l.startsWith('Admission:')));
      const f = await facts(page);
      check('the Morning desk reconciles the version-1 selection with its own words', !!f && !!f.detail && f.detail.unreviewedWord === 'mechanical A+/A', JSON.stringify(f));
      eq('no page errors on the retained record', errors, []);
    } finally { await context.close(); }
  }

  // shapes the generator never writes, each in a routed copy of the full night
  const cases = [
    ['half-written', (d) => { d.bursts.find((b) => b.ticker === 'MSFT').admission = { admitted: 'no' }; },
      // a block the page cannot read hides nothing and stops nothing
      async (page, where) => {
        eq(`${where}: an unreadable block hides nothing from the A-quality lens`, (await lensCounts(page)).a, admittedA.length + 1);
        check(`${where}: and stops nothing`, await page.evaluate(() => { const c = SCStock.model.stages.bursts.find((x) => x.ticker === 'MSFT'); return c.admitted === null && c.status !== 'route'; }));
        await page.evaluate(() => { location.hash = '#/explore/bursts/MSFT'; });
        await page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'bursts:MSFT');
        const why = await page.locator('#detail [data-item="why"] p').allTextContents();
        check(`${where}: the discovery sentence says the block is unreadable`, why.some((p) => p.includes('Admission: this record carries an admission block in a shape this page cannot read')), JSON.stringify(why));
        check(`${where}: the Morning desk does not reconcile a selection whose row contradicts its block`, unreconciled(await facts(page)), JSON.stringify(await facts(page)));
      }],
    ['blocker-dropped', (d) => { const b = d.bursts.find((x) => x.ticker === 'MSFT'); b.review_selection.blockers = []; b.review_selection.feasible = true; b.review_selection.purpose = 'budget_not_selected'; },
      async (page, where) => {
        check(`${where}: a selection that forgot the route blocker is not reconciled`, unreconciled(await facts(page)), JSON.stringify(await facts(page)));
      }],
    ['checks-contradict', (d) => { const b = d.bursts.find((x) => x.ticker === 'MSFT'); for (const c of b.quality.checks) if (c.letter === 'RE' || c.letter === 'VOL') { c.passed = true; c.pass = true; } },
      async (page, where) => {
        check(`${where}: a row whose checks say admitted while its block says stopped is not reconciled`, unreconciled(await facts(page)), JSON.stringify(await facts(page)));
        eq(`${where}: but the lens still prints the block the record wrote`, (await lensCounts(page)).a, admittedA.length);
      }],
    ['block-forged-admitted', (d) => { const b = d.bursts.find((x) => x.ticker === 'MSFT'); b.admission = { ...b.admission, admitted: true, basis: 'burst_route', reason: 'admitted by the 4% scan' }; },
      // the block says admitted while the route and the checks say stopped and the blockers agree with the checks:
      // the page prints the block it was given, and the desk refuses to reconcile it
      async (page, where) => {
        eq(`${where}: the lens prints the block the record wrote`, (await lensCounts(page)).a, admittedA.length + 1);
        check(`${where}: the Morning desk does not reconcile a block the row's own route and checks contradict`, unreconciled(await facts(page)), JSON.stringify(await facts(page)));
      }],
    ['blocker-forged-consistently', (d) => {
      // the receipt and the row agree with each other and not with the row's route: the route blocker gone,
      // the name in the research pool, every count moved to match
      const b = d.bursts.find((x) => x.ticker === 'MSFT');
      const decision = { ...b.review_selection, blockers: ['preview_unavailable'], research_pool: true, purpose: 'research_cap_not_selected' };
      b.review_selection = decision; b.evidence.review_selection = { ...b.evidence.review_selection, blockers: decision.blockers, research_pool: true, purpose: decision.purpose };
      const s = d.run.review_selection; s.blockers.route_not_admitted -= 1; s.blockers.preview_unavailable += 1; s.research_pool += 1; },
      async (page, where) => {
        check(`${where}: a receipt forged consistently without the route blocker is refused by the row's own route`, unreconciled(await facts(page)), JSON.stringify(await facts(page)));
      }],
    ['one-check-passes', (d) => { const b = d.bursts.find((x) => x.ticker === 'MSFT'); for (const c of b.quality.checks) if (c.letter === 'RE') { c.passed = true; c.pass = true; } },
      // range expansion alone is not admission: the block still says stopped, the route re-derives stopped, and the desk reconciles
      async (page, where) => {
        eq(`${where}: one passing check is still stopped`, (await lensCounts(page)).a, admittedA.length);
        const f = await facts(page);
        check(`${where}: and the desk still reconciles the selection`, !!f && !!f.detail && f.detail.unreviewedWord === 'admitted mechanical A+/A', JSON.stringify(f));
      }],
    ['no-admission-rule', (d) => { delete d.rules.admission; d.bursts.forEach((b) => { delete b.admission; }); delete d.run.admission; },
      async (page, where) => {
        eq(`${where}: without the rule every A is in the lens`, (await lensCounts(page)).a, allA.length);
        await page.evaluate(() => SCStock.navigate('#/method'));
        check(`${where}: Method names a record from before the rule`, (await methodLines(page)).some((l) => l.startsWith('Admission rule: this record predates')));
      }],
    ['other-checks', (d) => { d.rules.admission = { ...d.rules.admission, dollar_checks: ['RE', 'C'] }; },
      // the rule line names the checks the record archived and describes only the two it knows
      async (page, where) => {
        await page.evaluate(() => SCStock.navigate('#/method'));
        const line = (await methodLines(page)).find((l) => l.startsWith('Admission rule, as this record archived it'));
        check(`${where}: the rule line names the archived checks without describing checks it does not know`, !!line && line.includes('passes the checklist’s RE and C checks. Admission') && !line.includes('prior five sessions'), line);
      }],
    ['unknown-rule-shape', (d) => { d.rules.admission = { version: 2 }; },
      async (page, where) => {
        await page.evaluate(() => SCStock.navigate('#/method'));
        check(`${where}: a rule in a shape the page cannot read is said so`, (await methodLines(page)).some((l) => l === 'Admission rule: this record archives an admission rule in a shape this page cannot read.'));
      }],
  ];
  for (const [name, mutate, run] of cases) {
    const record = clone(full);
    mutate(record);
    const r = routed(name, record);
    const { page, context, errors } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, reducedMotion: 'reduce' });
    try {
      await run(page, name);
      eq(`${name}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
}
