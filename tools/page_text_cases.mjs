/* What the page says in its own words about rules the modules own, read back
   in Chromium. A veto is printed as the checklist measured it (rising closes,
   with the row's own count); the Method view names the gates this record
   archived, its one price source, its event registry, what the rules digest
   covers and that SpicyStock is a view; the Market view prints all five
   regime rules as the record's inputs read, and no scaled threshold as
   Bonde's own number; a burst ticket's exits name whose rule each is and say
   which figure of the day-1 line is the skip line; a listed row with no plan
   whose ticker is in the record's ARCHIVED event registry wears a known-deal
   flag, by the module's own interval rule (the parity corpus under
   tests/fixtures/event-registry/); the Record view says what is counted and
   how a stop is booked; the footer links the analyst brief at run time.
   Lane B: this suite writes no scratch record and reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const FIXTURES = path.resolve('tests/fixtures/page');
const PARITY = path.resolve('tests/fixtures/event-registry/classify-parity.json');
const REPO_BLOB = 'https://github.com/spicyChicken59/SpicyStock/blob/main/';

const clone = (d) => JSON.parse(JSON.stringify(d));
const usd = (v) => '$' + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const num = (v) => String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const plain = (v) => String(v).replace(/\.0$/, '');

// a record served from memory in place of a fixture, so a shape the generator
// never writes can be put in front of the page
function routed(name, record) {
  const body = JSON.stringify(record);
  return { url: `/pagetext-${name}.json`, beforeLoad: (p) => p.route(`**/pagetext-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) };
}
// textContent, so a closed disclosure's words are read too
const words = (page, sel) => page.locator(sel).evaluateAll((nodes) => nodes.map((n) => n.textContent));
const first = async (page, sel) => (await words(page, sel))[0] || '';
async function toStock(page, stage, ticker) {
  await page.evaluate((h) => { location.hash = h; }, `#/explore/${stage}/${ticker}`);
  await page.waitForFunction((id) => document.querySelector('#detail').dataset.selected === id, `${stage}:${ticker}`);
}
const toView = (page, view) => page.evaluate((h) => SCStock.navigate(h), '#/' + view);
// a node the page may not have drawn is a named failure, never a locator timeout that ends the suite
const within = async (page, sel, fn, absent) => ((await page.locator(sel).count()) ? page.locator(sel).first().evaluate(fn) : absent);

// ------------------------------------------------------------------ the veto
async function veto({ browser, base, open, check, eq, full, shotsDir }) {
  const mark = (d, values, archived) => {
    const b = d.bursts.find((x) => x.ticker === 'PLUG');
    b.vetoes = ['up_days']; b.quality.vetoes = ['up_days']; b.grade = 'skip'; b.quality.grade = 'skip';
    const two = b.quality.checks.find((x) => x.key === 'two_days');
    two.values = values;
    if (archived !== undefined) d.rules.quality.veto_up_days = archived;
    return d;
  };
  const cases = [
    // four rising closes, none a counted up day: the shape the audit found
    ['counted', mark(clone(full), { up_run: 0, up_closes: 4, prior_day_pct: 0.31 }),
      '4 rising closes in a row before the burst (three or more of any size refuse a setup)'],
    // a record whose check carries no count says the rule, with no count invented
    ['uncounted', mark(clone(full), { up_run: 0, prior_day_pct: 0.31 }), 'three or more rising closes in a row before the burst, of any size'],
    // the threshold is the record's own: one archived at four says four, and a count under it is not a veto's
    ['archived-four', mark(clone(full), { up_run: 0, up_closes: 3, prior_day_pct: 0.31 }, 4), 'four or more rising closes in a row before the burst, of any size'],
    ['archived-four-counted', mark(clone(full), { up_run: 0, up_closes: 5, prior_day_pct: 0.31 }, 4), '5 rising closes in a row before the burst (four or more of any size refuse a setup)']
  ];
  check('the fixture carries no vetoed burst of its own', full.bursts.every((b) => !(b.vetoes || []).length && !(b.quality.vetoes || []).length));
  for (const [name, record, want] of cases) {
    const r = routed('veto-' + name, record);
    const width = name === 'counted' ? 390 : 1280;
    const { page, context, errors } = await open(browser, base, r.url, NOW, width, { beforeLoad: r.beforeLoad, lens: 'all', reducedMotion: 'reduce', theme: name === 'counted' ? 'light' : 'dark' });
    try {
      const where = `veto ${name}`;
      await toStock(page, 'bursts', 'PLUG');
      eq(`${where}: the model's reason says the veto as measured`, await page.evaluate(() => SCStock.model.byId['bursts:PLUG'].reason), 'veto: ' + want);
      eq(`${where}: the checklist note says it`, await first(page, '#disc-checklist [data-veto-note]'), 'Veto: ' + want + '.');
      const blockers = await words(page, '#detail [data-item="wait"] [data-all-blockers] li');
      check(`${where}: the wait list says it`, blockers.includes('Quality veto: ' + want + '.'), JSON.stringify(blockers));
      const waits = await words(page, '#detail [data-item="wait"] p');
      check(`${where}: the wait item's own sentence says it`, waits.some((p) => p === 'Veto: ' + want + '.'), JSON.stringify(waits));
      // the saved setup's frozen limitations
      const add = page.locator('#detail .ss-follow button[data-follow-action="add"]');
      await add.click();
      await page.waitForFunction(() => SCStock.follow.list().some((x) => x.ticker === 'PLUG'), null, { timeout: 5000 });
      const limits = await page.evaluate(() => SCStock.follow.list().find((x) => x.ticker === 'PLUG').snapshot.limitations);
      check(`${where}: a saved setup freezes it`, limits.includes('veto: ' + want), JSON.stringify(limits));
      // the scan matrix
      await page.locator('#scan-summary').click();
      await page.waitForFunction((n) => document.querySelectorAll('#scan-table tbody tr').length === n, record.bursts.length);
      const note = await first(page, '#scan-table tbody tr[data-ticker="PLUG"] .ss-grade-note');
      check(`${where}: the scan matrix says it`, note.includes('veto · ' + want), note);
      const all = await page.evaluate(() => document.body.textContent);
      check(`${where}: nowhere does the page say "up days in a row"`, !all.includes('up days in a row'), 'the old words are on the page');
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir && name === 'counted') {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#disc-checklist').evaluate((n) => { n.open = true; n.scrollIntoView(); });
        await page.screenshot({ path: path.join(shotsDir, `pagetext-veto-${width}.png`), fullPage: false });
      }
      eq(`${where}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
}

// ------------------------------------------------------------------ the Method view
function registryWant(record) {
  // an independent reading of the archived registry, by the rule src/event_risk.py classify() states
  const reg = record.rules.event_risk.registry, session = record.run.session;
  const inForce = reg.events.filter((e) => session >= e.active_from && !(e.active_until && session >= e.active_until));
  const overdue = inForce.filter((e) => session > e.review_due);
  const days = Math.round((Date.parse(session + 'T12:00:00Z') - Date.parse(reg.reviewed_on + 'T12:00:00Z')) / 86400000);
  const n = reg.events.length;
  const state = !inForce.length ? 'none is in force at this session'
    : overdue.length ? `${overdue.length} of the ${inForce.length} in force at this session ${overdue.length === 1 ? 'is past its review date and stays blocked' : 'are past their review dates and stay blocked'}`
      : `none of the ${inForce.length} in force at this session is past its review date (next due ${inForce.map((e) => e.review_due).sort()[0]})`;
  return `Event registry: ${n} known cash-acquisition ${n === 1 ? 'entry' : 'entries'}, a manual list last reviewed ${reg.reviewed_on}` +
    (days >= 0 ? ` (${days} day${days === 1 ? '' : 's'} before this session)` : ' (after this session)') + `; ${state}. It is not a news screen: a stock that is not listed has not been cleared.`;
}
async function method({ browser, base, open, check, eq, full, shotsDir }) {
  const GATES = 'Discovery uses this record’s 4% breakout or Dollar breakout rules. A Dollar candidate can qualify below +4%; A-quality is judged after discovery. ' +
    'A candidate only the Dollar scan found is admitted to a plan or a chart read only under the admission rule printed under Published run (a range-expansion, higher-volume day). ' +
    'A grade is a weighted assessment, not a probability or an executable order. A burst ticket also needs a permitted market regime and a grade in the band it admits, no veto, ' +
    'an accepted chart review, a stop within 4% of its limit, no entry in the event registry, a whole share, a free slot, valid publication and an unexpired entry window.';
  const ROLE = 'SpicyStock is a view and a daily output: it lists candidates and what its rules say about them, and it places no order. An outside analyst and the owner decide what, if anything, to trade.';
  check('the fixture archives the rules the gates sentence names', full.rules.admission.dollar_checks.join(',') === 'RE,VOL' && full.rules.pipeline.reader_policy === 'accepted_required_v1' &&
    full.rules.plan.max_stop_pct === 4 && full.rules.plan.sizing_basis === 'order_limit' && !!full.rules.event_risk.registry.events.length, JSON.stringify(full.rules.admission));
  for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { theme, reducedMotion: 'reduce' });
    try {
      const where = `method ${width}`;
      await toView(page, 'method');
      eq(`${where}: the gates sentence names each gate this record archived`, await first(page, '#method-body [data-method-gates]'), GATES);
      eq(`${where}: one sentence says SpicyStock is a view and who decides`, await first(page, '#method-body [data-method-role]'), ROLE);
      const sheet = '#method-body a[data-rule-sheet]';
      eq(`${where}: the rule sheet is linked beside the method links`, await within(page, sheet, (a) => [a.getAttribute('href'), a.textContent], null), [REPO_BLOB + 'knowledge/rules.md', 'Every rule the run applies, in order (knowledge/rules.md)']);
      check(`${where}: in the paragraph that links the method and the rulebook`, await within(page, sheet, (a) => a.parentElement.querySelectorAll('a').length === 4 && a.parentElement.textContent.includes('knowledge/method.md') && a.parentElement.textContent.includes('knowledge/strategy.md'), false));
      eq(`${where}: the strategy page is linked beside them`, await within(page, sheet, (a) => { const s = a.parentElement.querySelector('a[data-strategy-page]'); return s ? [s.getAttribute('href'), s.textContent] : null; }, null), ['strategy.html', 'The strategy as the record’s rules state it (strategy.html)']);
      eq(`${where}: one line says the bars are one provider's, as of the fetch`, await first(page, '#run-meta [data-method-line="price-source"]'),
        `One price source: these bars are ${full.run.input_basis.provider}’s as this run fetched them (the run’s own clock reads ${full.run.published_at}). No second source cross-checks a close, a volume or a split, and the provider can revise a session’s bar afterwards; the next run reads the session again.`);
      eq(`${where}: one line reads the archived event registry`, await first(page, '#run-meta [data-method-line="event-registry"]'), registryWant(full));
      eq(`${where}: the digest line says what the digest covers`, await first(page, '#run-meta [data-method-line="rules-digest"]'),
        `Rules ${full.app.rules_version}: a digest of this record’s archived rules and its universe membership identity (${full.rules.universe.identity}); it moves on any night the membership moves. A changed digest can reflect membership alone; it does not by itself mean a rule changed.`);
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#method-body').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(shotsDir, `pagetext-method-${width}-${theme}.png`), fullPage: true });
      }
      eq(`${where}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
  // the fixture's own line, spelled out once so the derivation above cannot agree with a wrong page by itself.
  // Only the review date is read off the record: it moves with every registry review (the fixtures archive the
  // registry), and a literal there turned this check red on the review of 25 November 2026.
  const reviewedOn = full.rules.event_risk.registry.reviewed_on;
  check('the fixture archives the registry review date', /^\d{4}-\d{2}-\d{2}$/.test(reviewedOn) && reviewedOn > full.run.session);
  eq('the fixture registry line, as a literal', registryWant(full), `Event registry: 7 known cash-acquisition entries, a manual list last reviewed ${reviewedOn} (after this session); none of the 3 in force at this session is past its review date (next due 2026-10-15). It is not a news screen: a stock that is not listed has not been cleared.`);

  const shapes = [
    // a review a week before the session, two of three entries in force past their dates
    ['overdue', (d) => { const reg = d.rules.event_risk.registry; reg.reviewed_on = '2026-09-03'; reg.events.forEach((e) => { if (e.symbol === 'ARX' || e.symbol === 'ZIM') e.review_due = '2026-09-09'; }); },
      async (page, d) => {
        eq('method overdue: the count of entries past their review dates, of those in force', await first(page, '#run-meta [data-method-line="event-registry"]'),
          'Event registry: 7 known cash-acquisition entries, a manual list last reviewed 2026-09-03 (7 days before this session); 2 of the 3 in force at this session are past their review dates and stay blocked. It is not a news screen: a stock that is not listed has not been cleared.');
        eq('method overdue: and it is the independent reading', registryWant(d), await first(page, '#run-meta [data-method-line="event-registry"]'));
      }],
    // a review due on the session itself is not past
    ['due-today', (d) => { const reg = d.rules.event_risk.registry; reg.reviewed_on = '2026-09-09'; reg.events.forEach((e) => { e.review_due = '2026-09-10'; }); },
      async (page) => check('method due-today: a review due on the session is not past', (await first(page, '#run-meta [data-method-line="event-registry"]')).includes('(1 day before this session); none of the 3 in force at this session is past its review date (next due 2026-09-10)'), await first(page, '#run-meta [data-method-line="event-registry"]'))],
    ['one-overdue', (d) => { d.rules.event_risk.registry.events.forEach((e) => { if (e.symbol === 'ZIM') e.review_due = '2026-09-09'; }); },
      async (page) => check('method one-overdue: one entry reads in the singular', (await first(page, '#run-meta [data-method-line="event-registry"]')).includes('; 1 of the 3 in force at this session is past its review date and stays blocked.'), await first(page, '#run-meta [data-method-line="event-registry"]'))],
    // a record from before the registry says so, and names no registry gate
    ['predates', (d) => { delete d.rules.event_risk; },
      async (page) => {
        eq('method predates: a record without a registry says it predates it', await first(page, '#run-meta [data-method-line="event-registry"]'), 'Event registry: this record predates it; no list of known deals was archived with it.');
        check('method predates: and the gates sentence names no registry gate', !(await first(page, '#method-body [data-method-gates]')).includes('event registry'), await first(page, '#method-body [data-method-gates]'));
      }],
    ['unreadable', (d) => { d.rules.event_risk.registry.events = 'seven'; },
      async (page) => eq('method unreadable: a registry the page cannot read flags nothing and says so', await first(page, '#run-meta [data-method-line="event-registry"]'), 'Event registry: this record archives a registry in a shape this page cannot read, so no listed stock is flagged from it.')],
    ['half-entry', (d) => { delete d.rules.event_risk.registry.events[0].review_due; },
      async (page) => check('method half-entry: an entry without its review date makes the registry unreadable, never current', (await first(page, '#run-meta [data-method-line="event-registry"]')).includes('in a shape this page cannot read'), await first(page, '#run-meta [data-method-line="event-registry"]'))],
    // each gate is named only when the record archived it
    ['older-rules', (d) => { delete d.rules.admission; delete d.rules.pipeline.reader_policy; delete d.rules.plan.max_stop_pct; delete d.rules.universe.identity; d.bursts.forEach((b) => { delete b.admission; }); delete d.run.admission; },
      async (page, d) => {
        eq('method older-rules: a record from before the admission, the review requirement and the stop line names none of them', await first(page, '#method-body [data-method-gates]'),
          'Discovery uses this record’s 4% breakout or Dollar breakout rules. A Dollar candidate can qualify below +4%; A-quality is judged after discovery. A grade is a weighted assessment, not a probability or an executable order. ' +
          'A burst ticket also needs a permitted market regime and a grade in the band it admits, no veto, no entry in the event registry, a whole share, a free slot, valid publication and an unexpired entry window.');
        eq('method older-rules: a record whose rules nest no membership identity says only what its digest covers', await first(page, '#run-meta [data-method-line="rules-digest"]'), `Rules ${d.app.rules_version}: a digest of this record’s archived rules.`);
      }],
    ['other-checks', (d) => { d.rules.admission.dollar_checks = ['RE', 'C']; },
      async (page) => check('method other-checks: the admission is described as range and volume only when those are the archived checks', !(await first(page, '#method-body [data-method-gates]')).includes('range-expansion') && (await first(page, '#method-body [data-method-gates]')).includes('only under the admission rule printed under Published run.'), await first(page, '#method-body [data-method-gates]'))],
    ['other-stop', (d) => { d.rules.plan.max_stop_pct = 3.5; },
      async (page) => check('method other-stop: the stop line is the record’s own number', (await first(page, '#method-body [data-method-gates]')).includes('a stop within 3.5% of its limit'), await first(page, '#method-body [data-method-gates]'))]
  ];
  for (const [name, mutate, then] of shapes) {
    const d = clone(full); mutate(d);
    const r = routed('method-' + name, d);
    const { page, context, errors } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'method');
      await then(page, d);
      eq(`method ${name}: no page errors`, errors.filter((e) => !/provenance|evidence/i.test(e)), []);
    } finally { await context.close(); }
  }
}

// ------------------------------------------------------------------ the Market view
function rulesWant(record) {
  // the five rules of src/breadth.py regime(), read independently off the record
  const reg = record.breadth.regime, th = reg.thresholds, x = reg.inputs;
  return {
    down4_alarm: ['red', x.down4 >= th.down4_alarm], ratio_10d_red: ['red', x.ratio_10d !== null && x.ratio_10d < th.ratio_10d_red],
    ratio_5d_red: ['red', x.ratio_5d !== null && x.ratio_5d < th.ratio_5d_red && x.down4 > x.up4],
    ratio_10d_yellow: ['yellow', x.ratio_10d !== null && x.ratio_10d < th.ratio_10d_yellow], up50_month_hot: ['yellow', x.up50_month > th.up50_month_hot]
  };
}
// five rows whatever the page drew, so a page that prints no list fails each check by name
const rulesRead = async (page) => {
  const rows = await page.locator('#regime [data-regime-rules] li').evaluateAll((nodes) => nodes.map((n) => [n.dataset.regimeRule, n.dataset.tier, n.dataset.fired === 'true', n.textContent]));
  while (rows.length < 5) rows.push([null, null, null, '']);
  return rows;
};
async function market({ browser, base, open, check, eq, full, shotsDir }) {
  for (const variant of ['full', 'yellow', 'red']) {
    const record = JSON.parse(await readFile(path.join(FIXTURES, `${variant}.json`), 'utf8'));
    const reg = record.breadth.regime, th = reg.thresholds, x = reg.inputs, rules = record.breadth.rules;
    for (const width of variant === 'red' ? [1280, 390] : [1280]) {
      const { page, context, errors } = await open(browser, base, `/tests/fixtures/page/${variant}.json`, NOW, width, { reducedMotion: 'reduce', theme: width === 390 ? 'light' : 'dark' });
      try {
        const where = `market ${variant} ${width}`;
        await toView(page, 'market');
        const read = await rulesRead(page), want = rulesWant(record);
        eq(`${where}: all five rules are printed, in the order the run evaluates them`, read.map((r) => r[0]), ['down4_alarm', 'ratio_10d_red', 'ratio_5d_red', 'ratio_10d_yellow', 'up50_month_hot']);
        eq(`${where}: each with its tier and whether it fired`, read.map((r) => [r[0], r[1], r[2]]), Object.entries(want).map(([k, v]) => [k, v[0], v[1]]));
        // the record's own reasons are an independent count: every rule on a green night, the fired rules of the verdict's tier otherwise
        const firedInTier = read.filter((r) => r[1] === reg.verdict && r[2]).length;
        eq(`${where}: the fired rules of the verdict's tier are as many as the record's own reasons`, reg.verdict === 'green' ? [read.filter((r) => r[2]).length, reg.reasons.length] : [firedInTier, reg.reasons.length], reg.verdict === 'green' ? [0, 5] : [reg.reasons.length, reg.reasons.length]);
        const alarm = read[0][3], hot = read[4][3];
        eq(`${where}: the scaled alarm is printed with its measured value, fired or not`, alarm,
          `red · ${want.down4_alarm[1] ? 'fired' : 'not fired'} names down 4% today: ${num(x.down4)} against the scaled alarm of ${plain(th.down4_alarm)} (${num(rules.down4_alarm)} per ${num(th.reference_universe)}, over ${num(th.universe)} measured); it fires at or over the alarm.`);
        eq(`${where}: the scaled hot mark is printed with its measured value`, hot,
          `yellow · ${want.up50_month_hot[1] ? 'fired' : 'not fired'} names up 50% in a month: ${num(x.up50_month)} against the scaled hot mark of ${plain(th.up50_month_hot)} (${num(rules.up50_month_hot)} per ${num(th.reference_universe)}, over ${num(th.universe)} measured); it fires over the mark.`);
        check(`${where}: the ten-session ratio is read against both of its lines`, read[1][3].includes(`10-session ratio: ${plain(x.ratio_10d)} (${x.up4_10d} up, ${x.down4_10d} down) against ${plain(th.ratio_10d_red)}; it fires under it`) &&
          read[3][3].includes(`against ${plain(th.ratio_10d_yellow)}; it fires under it`), JSON.stringify([read[1][3], read[3][3]]));
        check(`${where}: the five-session rule names today's counts`, read[2][3].includes(`5-session ratio: ${plain(x.ratio_5d)} (${x.up4_5d} up, ${x.down4_5d} down) against ${plain(th.ratio_5d_red)}, with ${x.down4} down and ${x.up4} up today; it fires under it only with more down than up today`), read[2][3]);
        for (const r of reg.reasons) check(`${where}: the record's own reason still stands above`, (await first(page, '#regime > ul')).includes(r), r);
        check(`${where}: and the scaling is said to be SpicyStock's`, (await first(page, '#regime [data-regime-rules] .sc-hint')).includes('The two count thresholds are scaled by SpicyStock to the stocks measured that night; the ratios are not scaled.'));
        // the fact cards: a scaled number is never printed as Bonde's own
        const notes = Object.fromEntries(record.breadth.notes.map((n) => [n.key, n.text]));
        eq(`${where}: the froth note says what was scaled, then the note verbatim`, await first(page, '#breadth-facts [data-note="up50_month"]'),
          `The method notes quote Bonde’s reading as ${num(rules.up50_month_hot)} over ${num(th.reference_universe)} stocks; SpicyStock scales it to the ${num(th.universe)} measured: ${notes.up50_month}`);
        eq(`${where}: the oversold note says whose wording it is and what was scaled`, await first(page, '#breadth-facts [data-note="down25_quarter"]'),
          `A field guide’s wording, not checked against Bonde’s own, gives ${num(rules.down25_quarter_oversold)} over ${num(th.reference_universe)} stocks; SpicyStock scales it to the ${num(th.universe)} measured: ${notes.down25_quarter}`);
        eq(`${where}: an unscaled reading keeps its attribution`, await first(page, '#breadth-facts [data-note="pct_above_40ma"]'), 'Bonde: ' + notes.pct_above_40ma);
        const cards = (await words(page, '#breadth-facts .sc-note')).join('\n');
        check(`${where}: no scaled count is printed after "Bonde: "`, !/Bonde: (more|fewer) than/.test(cards), cards);
        eq(`${where}: the caption says the sessions are this run's re-reading and a verdict is never recomputed`, await first(page, '#ratio-chart [data-history-reread]'),
          `The ${record.breadth.history.length} sessions in this chart and its table are this run’s own re-reading over the stocks it measured on Thu 10 Sep, so an earlier session’s counts can differ from what that night published. A published verdict is never recomputed.`);
        check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
        if (shotsDir && variant === 'red') {
          await mkdir(shotsDir, { recursive: true });
          await page.screenshot({ path: path.join(shotsDir, `pagetext-market-${width}.png`), fullPage: true });
        }
        eq(`${where}: no page errors`, errors, []);
      } finally { await context.close(); }
    }
  }
  const red = JSON.parse(await readFile(path.join(FIXTURES, 'red.json'), 'utf8'));
  check('the red fixture is red on the scaled alarm alone, with a yellow rule also true under it', red.breadth.regime.reasons.length === 1 && rulesWant(red).ratio_10d_yellow[1] && !rulesWant(red).ratio_10d_red[1], JSON.stringify(red.breadth.regime.inputs));
  const shapes = [
    // inputs that do not give the record's verdict: the list is withheld, the record's reasons stand
    ['contradicted', (d) => { d.breadth.regime.inputs.down4 = 0; }, async (page, d) => {
      eq('market contradicted: rules that do not give the record’s verdict are not printed', await page.locator('#regime [data-regime-rules]').count(), 0);
      check('market contradicted: the record’s reasons still are', (await first(page, '#regime > ul')).includes(d.breadth.regime.reasons[0]));
    }],
    ['no-inputs', (d) => { delete d.breadth.regime.inputs; }, async (page) => eq('market no-inputs: a record without rule inputs prints no list', await page.locator('#regime [data-regime-rules]').count(), 0)],
    ['half-inputs', (d) => { d.breadth.regime.inputs.up50_month = 'none'; }, async (page) => eq('market half-inputs: a half-written input prints no list', await page.locator('#regime [data-regime-rules]').count(), 0)],
    // no name broke down in ten sessions: the ratio has no value and neither ratio rule fires
    ['no-ratio', (d) => { const g = d.breadth.regime; g.inputs.down4 = 0; g.inputs.ratio_10d = null; g.inputs.ratio_5d = null; g.verdict = 'green'; }, async (page) => {
      const read = await rulesRead(page);
      eq('market no-ratio: a ratio with no value fires no rule', read.map((r) => r[2]), [false, false, false, false, false]);
      check('market no-ratio: and is said to have none', read[1][3].includes('10-session ratio: none (') && read[2][3].includes('5-session ratio: none ('), JSON.stringify([read[1][3], read[2][3]]));
    }],
    // the five-session rule needs more down than up today
    ['fast-selling', (d) => { const g = d.breadth.regime; g.inputs.down4 = 1; g.inputs.up4 = 0; g.inputs.ratio_5d = 0.4; }, async (page) => {
      const read = await rulesRead(page);
      eq('market fast-selling: the five-session rule fires under its line with more down than up', [read[2][2], read[0][2]], [true, false]);
    }],
    ['slow-selling', (d) => { const g = d.breadth.regime; g.inputs.down4 = 1; g.inputs.up4 = 1; g.inputs.ratio_5d = 0.4; g.inputs.ratio_10d = 0.9; }, async (page) => {
      const read = await rulesRead(page);
      eq('market slow-selling: under its line with no more down than up it does not fire', [read[2][2], read[1][2]], [false, true]);
    }],
    // the boundaries: at the alarm fires, at the hot mark does not, at a ratio line does not
    ['boundaries', (d) => { const g = d.breadth.regime; g.inputs.down4 = 3.4; g.inputs.up50_month = 0.1; g.inputs.ratio_10d = 1.0; }, async (page) => {
      const read = await rulesRead(page);
      eq('market boundaries: at the alarm fires; at the hot mark and at a ratio line does not', [read[0][2], read[4][2], read[1][2]], [true, false, false]);
    }]
  ];
  for (const [name, mutate, then] of shapes) {
    const d = clone(red); mutate(d);
    const r = routed('market-' + name, d);
    const { page, context, errors } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'market');
      await then(page, d);
      eq(`market ${name}: no page errors`, errors.filter((e) => !/provenance|evidence/i.test(e)), []);
    } finally { await context.close(); }
  }
}

// ------------------------------------------------------------------ the stock detail
async function detail({ browser, base, open, check, eq, full, shotsDir }) {
  const trade = full.bursts.find((b) => b.ticker === full.trades[0]), plan = trade.plan;
  const BAND = `The buy stop triggers at ${usd(plan.entry_ref)} and can fill up to its ${usd(plan.limit)} limit; ${usd(plan.entry_low)} in the day-1 line is the skip line, not a buy price.`;
  check('the ticket’s order is a buy stop at its trigger with the limit above it', plan.order_json.stop_price === plan.entry_ref && plan.order_json.limit_price === plan.limit && plan.entry_low < plan.entry_ref && plan.entry_ref < plan.limit, JSON.stringify(plan.order_json));
  check('and its recorded day-1 line reads as a band from the skip line', plan.exit_schedule[0].instruction.includes(`inside ${usd(plan.entry_low)}–${usd(plan.limit)}`), plan.exit_schedule[0].instruction);
  for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { theme, lens: 'all', reducedMotion: 'reduce' });
    try {
      const where = `detail ${width}`;
      await toStock(page, 'bursts', trade.ticker);
      eq(`${where}: one sentence above the timeline says which figure is the skip line`, await first(page, '#disc-exits [data-entry-band]'), BAND);
      check(`${where}: it sits above the dated timeline`, await within(page, '#disc-exits [data-entry-band]', (p) => !!(p.compareDocumentPosition(p.parentElement.querySelector('.sc-timeline')) & Node.DOCUMENT_POSITION_FOLLOWING), false));
      check(`${where}: the record's own day-1 line is printed unchanged under it`, (await first(page, '#disc-exits .sc-timeline__item .sc-timeline__body')).toLowerCase() === (plan.exit_schedule[0].instruction).toLowerCase(), await first(page, '#disc-exits .sc-timeline__item .sc-timeline__body'));
      // the rules list, read by position so a page that marks no rule still has its words read
      const listed = await page.locator('#disc-exits ul.ss-notes li').evaluateAll((nodes) => nodes.map((n) => n.textContent));
      const exits = Object.fromEntries(plan.exits.map((x, i) => [x.key, listed[i] || '']));
      eq(`${where}: every exit rule the plan carries is listed, each marked with its rule`, [listed.length, await page.locator('#disc-exits [data-exit-rule]').evaluateAll((nodes) => nodes.map((n) => n.dataset.exitRule))], [plan.exits.length, plan.exits.map((x) => x.key)]);
      check(`${where}: Bonde's rules say so in words`, exits.sell_half_8pct.endsWith(' (Bonde, per the method notes)') && exits.day5_exit.endsWith(' (Bonde, per the method notes)'), exits.sell_half_8pct);
      check(`${where}: this build's reading says so`, exits.trail_after_day3.endsWith(' (this build’s reading)'), exits.trail_after_day3);
      check(`${where}: the break-even caution is a third party's test of another setup`, exits.no_breakeven.endsWith(' (a third party’s test of another setup, not measured on bursts)'), exits.no_breakeven);
      check(`${where}: no rule ends in a bare source letter`, Object.values(exits).every((t) => !/ \([A-Z]\)$/.test(t)), JSON.stringify(Object.values(exits).filter((t) => / \([A-Z]\)$/.test(t))));
      for (const x of plan.exits) check(`${where}: ${x.key} keeps the record's own words`, exits[x.key].toLowerCase().startsWith((x.when + ': ' + x.rule).toLowerCase()), exits[x.key]);
      const rulesRow = await page.locator('#disc-provenance .sc-facts > div').evaluateAll((rows) => rows.map((r) => [r.querySelector('dt').textContent, r.querySelector('dd').textContent]).find((r) => r[0] === 'rules'));
      eq(`${where}: the provenance row says what the rules digest covers`, rulesRow, ['rules', full.app.rules_version + 'a digest of this record’s archived rules and its universe membership identity; it moves on any night the membership moves']);
      // a withheld burst and a coil carry no such sentence: neither has the band line this one corrects
      await toStock(page, 'bursts', 'TSLA');
      eq(`${where}: a withheld burst prints no skip-line sentence`, await page.locator('#disc-exits [data-entry-band]').count(), 0);
      await toStock(page, 'setting-up', 'COIL');
      eq(`${where}: a coil prints no skip-line sentence`, await page.locator('#disc-exits [data-entry-band]').count(), 0);
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await toStock(page, 'bursts', trade.ticker);
        await page.locator('#disc-exits').evaluate((n) => { n.open = true; n.scrollIntoView(); });
        await page.screenshot({ path: path.join(shotsDir, `pagetext-detail-${width}-${theme}.png`), fullPage: false });
      }
      eq(`${where}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
  // a day-1 line that does not carry the skip figure, or a band that is not one, gets no sentence
  // each shape leaves every OTHER condition of the sentence true, so only the rule it names can refuse it
  const lineWith = (p, low) => { p.exit_schedule[0].instruction = p.exit_schedule[0].instruction.split(usd(plan.entry_low)).join(usd(low)); };
  const shapes = [
    ['other-line', (p) => { p.exit_schedule[0].instruction = 'buy through the trigger in the first 30 minutes.'; }],
    ['skip-at-trigger', (p) => { p.entry_low = p.entry_ref; lineWith(p, p.entry_ref); }],
    ['limit-at-trigger', (p) => { p.limit = p.entry_ref; }],
    ['no-limit', (p) => { p.limit = null; }]
  ];
  check('the two band shapes still carry their skip figure in the day-1 line', shapes.slice(1, 3).every(([, mutate]) => { const p = clone(plan); mutate(p); return p.exit_schedule[0].instruction.includes(usd(p.entry_low)); }));
  for (const [name, mutate] of shapes) {
    const d = clone(full); mutate(d.bursts.find((b) => b.ticker === trade.ticker).plan);
    const r = routed('detail-' + name, d);
    const { page, context } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, lens: 'all', reducedMotion: 'reduce' });
    try {
      await toStock(page, 'bursts', trade.ticker);
      eq(`detail ${name}: no skip-line sentence is composed`, await page.locator('#disc-exits [data-entry-band]').count(), 0);
    } finally { await context.close(); }
  }
  // a coil ticket never gets the sentence, even one whose plan and day-1 line carry a lower figure
  {
    const notrade = JSON.parse(await readFile(path.join(FIXTURES, 'notrade.json'), 'utf8'));
    const coil = notrade.watchlist.top.find((x) => x.ticker === 'COIL').plan;
    check('the no-trade night carries a coil ticket with a dated day-1 line', !!coil.order_json && coil.exit_schedule[0].key === 'entry' && coil.entry_ref < coil.limit, JSON.stringify(coil.order_json));
    const low = +(coil.entry_ref - 2).toFixed(2);
    coil.entry_low = low; coil.exit_schedule[0].instruction += ' Skip it under ' + usd(low) + '.';
    const rc = routed('detail-coil', notrade);
    const { page, context } = await open(browser, base, rc.url, NOW, 1280, { beforeLoad: rc.beforeLoad, lens: 'all', reducedMotion: 'reduce' });
    try {
      await toStock(page, 'setting-up', 'COIL');
      eq('detail coil: the stock is a ticket', await page.evaluate(() => SCStock.model.byId['setting-up:COIL'].status), 'ticket');
      eq('detail coil: a coil ticket prints no skip-line sentence, whatever its plan carries', await page.locator('#disc-exits [data-entry-band]').count(), 0);
    } finally { await context.close(); }
  }
  const older = clone(full); delete older.rules.universe.identity;
  const r = routed('detail-older', older);
  const { page, context } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, lens: 'all', reducedMotion: 'reduce' });
  try {
    await toStock(page, 'bursts', trade.ticker);
    check('detail older: a record whose rules nest no membership identity names none in its provenance row', (await first(page, '#disc-provenance .sc-facts')).includes(older.app.rules_version + 'a digest of this record’s archived rules') && !(await first(page, '#disc-provenance .sc-facts')).includes('membership'), await first(page, '#disc-provenance .sc-facts'));
  } finally { await context.close(); }
}

// ------------------------------------------------------------------ the known-deal flag
async function deals({ browser, base, open, check, eq, full, shotsDir }) {
  const parity = JSON.parse(await readFile(PARITY, 'utf8'));
  // the page's rule against the module's own answers, boundary days included
  {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, 1280, { reducedMotion: 'reduce' });
    try {
      const got = await page.evaluate(({ registry, cases }) => cases.map((c) => {
        if (typeof SCStock.registryMatch !== 'function') return null;
        const m = SCStock.registryMatch(c.symbol, c.session, registry);
        return m && { symbol: m.symbol, status: m.status, blocked: m.blocked, reason: m.reason, registry_reviewed_on: m.registry_reviewed_on,
          matches: m.matches.map((x) => ({ id: x.id, review_overdue: x.review_overdue, evidence_as_of: x.evidence_as_of, active_until: x.active_until === undefined ? null : x.active_until, sources: x.sources.map((s) => s.published_on), resolution: !!x.resolution })) };
      }), { registry: parity.registry, cases: parity.cases });
      const wrong = parity.cases.map((c, i) => [c, got[i]]).filter(([c, g]) => JSON.stringify(g) !== JSON.stringify(c.expect));
      check(`deals: the page's rule gives classify()'s answer on all ${parity.cases.length} corpus cases`, parity.cases.length > 100 && wrong.length === 0, JSON.stringify(wrong.slice(0, 2)));
      eq('deals: the corpus reaches every status', [...new Set(parity.cases.map((c) => c.expect.status))].sort(), ['known_event', 'not_in_registry', 'review_required']);
      eq('deals: a symbol the module refuses, a session that is not a date and a missing registry read as nothing, and a real case as something', await page.evaluate((registry) => { const f = SCStock.registryMatch; return typeof f === 'function' ? [f('1AB', '2026-03-12', registry), f('AAA', '2026-3-12', registry), f('AAA', '2026-02-30', registry), f('AAA', '2026-03-12', null), f('AAA', '2026-03-12', registry).status] : 'no registryMatch'; }, parity.registry), [null, null, null, null, 'known_event']);
      eq('deals: no page errors over the corpus', errors, []);
    } finally { await context.close(); }
  }
  // the record: an unplanned burst, an also-quiet coil and a planned ticket, each put in the archived registry
  const entry = (symbol, dates) => Object.assign({ id: 'synthetic-' + symbol.toLowerCase(), symbol, issuer: 'Synthetic issuer ' + symbol, kind: 'cash_acquisition',
    announced_on: '2026-08-20', active_from: '2026-08-20', active_until: null, evidence_as_of: '2026-09-01', reviewed_on: '2026-09-02', review_due: '2026-09-17',
    reason: 'Synthetic entry for ' + symbol + ': a pending cash deal invented for this check.',
    sources: [{ title: 'Synthetic announcement', published_on: '2026-08-20', url: 'https://example.invalid/synthetic/a', sha256: 'a'.repeat(64), quote: 'Synthetic quote; not a real filing.' },
      { title: 'Synthetic update after the session', published_on: '2026-09-11', url: 'https://example.invalid/synthetic/b', sha256: 'b'.repeat(64), quote: 'Synthetic later quote.' }] }, dates || {});
  const build = (events) => {
    const d = clone(full);
    d.rules.event_risk.registry.events = d.rules.event_risk.registry.events.concat(events);
    const coil = clone(d.watchlist.top[0]); coil.ticker = 'QUIET'; coil.name = 'Synthetic quiet coil'; delete coil.plan;
    d.watchlist.also_quiet = [coil];
    return d;
  };
  const record = build([entry('PLUG'), entry('QUIET', { review_due: '2026-09-09' }), entry('AAPL'), entry('DLLR', { active_from: '2026-09-11' })]);
  const r = routed('deals', record);
  for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
    const { page, context, errors } = await open(browser, base, r.url, NOW, width, { beforeLoad: r.beforeLoad, lens: 'all', theme, reducedMotion: 'reduce' });
    try {
      const where = `deals ${width}`;
      const card = (stage, t) => page.locator(`#pick-list .ss-pick[data-ticker="${t}"]`).evaluate((b) => [b.dataset.deal || null, b.dataset.status, Array.from(b.querySelectorAll('.ss-pick__row .sc-chip')).map((c) => c.textContent).pop()]);
      eq(`${where}: an unplanned burst in the archived registry wears the flag where its status chip sits`, await card('bursts', 'PLUG'), ['known_event', 'below_grade', 'known deal']);
      eq(`${where}: a planned ticket in the registry wears none of the page's: the record's own plan governs`, await card('bursts', 'AAPL'), [null, 'ticket', 'ticket']);
      eq(`${where}: an entry that starts after the session flags nothing`, (await card('bursts', 'DLLR'))[0], null);
      eq(`${where}: a burst that is not in the registry wears no flag`, (await card('bursts', 'MSFT'))[0], null);
      const plain = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
      check(`${where}: the flagged card is no taller than the same card without the flag`, await page.evaluate(() => { const a = document.querySelector('#pick-list .ss-pick[data-ticker="PLUG"]'), b = document.querySelector('#pick-list .ss-pick[data-ticker="DLLR"]'); return a.getBoundingClientRect().height <= b.getBoundingClientRect().height + 1; }), 'the flag grew the card');
      check(`${where}: (the unflagged fixture has no such chip at all)`, !JSON.stringify(plain.rules.event_risk.registry.events.map((e) => e.symbol)).includes('PLUG'));
      await toStock(page, 'bursts', 'PLUG');
      eq(`${where}: the detail's own chips carry the flag beside the status`, await page.locator('#detail .ss-detail__chips .sc-chip').evaluateAll((chips) => chips.filter((c) => c.dataset.deal).map((c) => [c.dataset.deal, c.textContent])), [['known_event', 'known deal']]);
      const risk = await words(page, '#detail [data-item="risk"] > p');
      eq(`${where}: the detail prints the registry's own reason, composed as the module composes it`, risk[0], 'In this record’s event registry: Known cash-acquisition event: Synthetic entry for PLUG: a pending cash deal invented for this check.');
      const sources = '#detail [data-item="risk"] [data-event-sources]';
      eq(`${where}: with its sources disclosure`, await page.locator(sources).count(), 1);
      const listed = await within(page, sources, (n) => n.textContent, '');
      check(`${where}: naming the registry's review and the entry's own review date`, listed.includes('Recorded registry review: ' + record.rules.event_risk.registry.reviewed_on) && listed.includes('review due 2026-09-17') && !listed.includes('overdue'), listed);
      check(`${where}: and only the source published by the session`, listed.includes('Synthetic announcement') && !listed.includes('Synthetic update after the session') && listed.includes('evidence through 2026-08-20'), listed);
      eq(`${where}: no order is offered for it`, await page.locator('#detail [data-order], #detail [data-copy]').count(), 0);
      // a saved setup freezes the flag with its other limitations
      if (await page.locator('#detail .ss-follow button[data-follow-action="add"]').count()) {
        await page.locator('#detail .ss-follow button[data-follow-action="add"]').click();
        await page.waitForFunction(() => SCStock.follow.list().some((x) => x.ticker === 'PLUG'), null, { timeout: 5000 }).catch(() => {});
      }
      const frozen = await page.evaluate(() => { const it = SCStock.follow.list().find((x) => x.ticker === 'PLUG'); return it ? it.snapshot.limitations : null; });
      check(`${where}: a saved setup freezes the flag in the registry's words`, !!frozen && frozen.includes('in that record’s event registry: Known cash-acquisition event: Synthetic entry for PLUG: a pending cash deal invented for this check.'), JSON.stringify(frozen));
      // the also-quiet coil, its review past its date
      await page.evaluate(() => { location.hash = '#/explore/setting-up/QUIET'; });
      await page.waitForFunction(() => document.querySelector('#detail').dataset.selected === 'setting-up:QUIET');
      eq(`${where}: an also-quiet coil past its review date wears the flag as review_required`, await card('setting-up', 'QUIET'), ['review_required', 'watch', 'known deal']);
      const quiet = await words(page, '#detail [data-item="risk"] > p');
      eq(`${where}: and its reason carries the module's overdue sentence`, quiet[0], 'In this record’s event registry: Known cash-acquisition event: Synthetic entry for QUIET: a pending cash deal invented for this check. The manual review is overdue; new entries remain withheld pending a source review.');
      check(`${where}: its sources say the entry stays withheld`, (await within(page, sources, (n) => n.textContent, '')).includes('review due 2026-09-09 · overdue; entries remain withheld'));
      // the planned ticket keeps the record's own evidence and nothing of the page's
      await toStock(page, 'bursts', 'AAPL');
      eq(`${where}: a row with a plan wears no flag in its header`, await page.locator('#detail .ss-detail__chips [data-deal]').count(), 0);
      const mine = await words(page, '#detail [data-item="risk"] > p');
      check(`${where}: a row with a plan prints no registry sentence of the page's`, !mine.join(' ').includes('In this record’s event registry'), JSON.stringify(mine));
      eq(`${where}: the model carries the flag only on rows without a plan`, await page.evaluate(() => ['bursts:PLUG', 'bursts:AAPL', 'bursts:DLLR', 'setting-up:QUIET', 'setting-up:COIL'].map((id) => { const c = SCStock.model.byId[id]; return c && c.deal ? c.deal.status : null; })), ['known_event', null, null, 'review_required', null]);
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await toStock(page, 'bursts', 'PLUG');
        await page.screenshot({ path: path.join(shotsDir, `pagetext-deal-${width}-${theme}.png`), fullPage: false });
      }
      eq(`${where}: no page errors`, errors.filter((e) => !/provenance|evidence/i.test(e)), []);
    } finally { await context.close(); }
  }
  // the interval's boundary days over the record's own session (10 Sep 2026)
  const boundaries = [
    ['starts-today', { active_from: '2026-09-10', announced_on: '2026-09-10' }, 'known_event'],
    ['ended-today', { active_until: '2026-09-10' }, null],
    ['ends-tomorrow', { active_until: '2026-09-11' }, 'known_event'],
    ['due-today', { review_due: '2026-09-10' }, 'known_event'],
    ['due-yesterday', { review_due: '2026-09-09' }, 'review_required']
  ];
  for (const [name, dates, want] of boundaries) {
    const d = build([entry('PLUG', dates)]);
    const rr = routed('deals-' + name, d);
    const { page, context } = await open(browser, base, rr.url, NOW, 1280, { beforeLoad: rr.beforeLoad, lens: 'all', reducedMotion: 'reduce' });
    try {
      eq(`deals ${name}: the flag is ${want || 'absent'}`, await page.evaluate(() => { const c = SCStock.model.byId['bursts:PLUG']; return c.deal ? c.deal.status : null; }), want);
      eq(`deals ${name}: and the card says the same`, await page.locator('#pick-list .ss-pick[data-ticker="PLUG"]').getAttribute('data-deal'), want);
    } finally { await context.close(); }
  }
  // a registry the page cannot read flags nothing, and a record without one flags nothing
  for (const [name, mutate] of [['unreadable', (d) => { d.rules.event_risk.registry.events.push({ symbol: 'PLUG' }); }], ['predates', (d) => { delete d.rules.event_risk; }]]) {
    const d = build([entry('PLUG')]); mutate(d);
    const rr = routed('deals-' + name, d);
    const { page, context } = await open(browser, base, rr.url, NOW, 1280, { beforeLoad: rr.beforeLoad, lens: 'all', reducedMotion: 'reduce' });
    try {
      eq(`deals ${name}: no row is flagged`, await page.locator('#pick-list .ss-pick[data-deal]').count(), 0);
    } finally { await context.close(); }
  }
}

// ------------------------------------------------------------------ the Record view and the footer
async function recordView({ browser, base, open, check, eq, full, shotsDir }) {
  const COUNTED = 'Every retained ticket is counted once for each night it was issued: a setup issued again on a later night is a new ticket and is counted again, and a ticket a later run of the same session withdrew stays counted.';
  const BOOKED = 'No fees, spread, slippage, tax or actual execution are measured. A stop first reached inside a session is booked at exactly the stop price, so a stop on the fill day is always exactly minus one R whatever that day’s low or close; only a session that opens at or under the stop is booked at its open. R is counted per ticket whatever its size, and whole-share sales make it depend on the share count (a one-share ticket sells whole at its half-sale), so a sum of R is not a sum of dollars.';
  const MINUTES = `; a first day the daily bar cannot place is read again from that session’s retained one-minute bars, which place a fill only inside the plan’s first ${full.rules.intraday.window_minutes} minutes (rule ${full.rules.record.intraday_fill})`;
  for (const [width, theme] of [[1280, 'dark'], [390, 'light']]) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', NOW, width, { theme, reducedMotion: 'reduce' });
    try {
      const where = `record ${width}`;
      await toView(page, 'record');
      const accounting = await first(page, '#record-card [data-scorecard-accounting]');
      check(`${where}: the accounting says what is counted`, accounting.endsWith(' missing or stale observations. ' + COUNTED) && !accounting.includes('Every published plan is counted once'), accounting);
      check(`${where}: the calculation says how a stop is booked and that a sum of R is not a sum of dollars`, (await first(page, '#record-card [data-scorecard-booking]')).startsWith(BOOKED), await first(page, '#record-card [data-scorecard-booking]'));
      check(`${where}: the replay prices name the one-minute bars that place a first-day fill`, (await first(page, '#record-card [data-scorecard-prices]')).startsWith(`Replay prices: ${full.scorecard.input_basis.adjustment}-adjusted daily bars · ${full.scorecard.input_basis.feed}${MINUTES}. Frozen original levels`), await first(page, '#record-card [data-scorecard-prices]'));
      check(`${where}: and so does the model-plans hint`, (await first(page, '#hold-hint')).includes('walked from daily bars, and from retained one-minute bars where a first day needs them, by the published ticket’s own rules.'), await first(page, '#hold-hint'));
      // the footer: the brief's two files, linked by the script
      const links = await page.locator('#foot-line a[data-brief]').evaluateAll((nodes) => nodes.map((a) => [a.getAttribute('href'), a.textContent]));
      eq(`${where}: the footer links the analyst brief and its JSON`, links, [['brief.md', 'analyst brief'], ['brief.json', 'brief.json']]);
      // the page asks nothing of the files, so each link says when it can be absent
      const titles = await page.locator('#foot-line a[data-brief]').evaluateAll((nodes) => nodes.map((a) => a.getAttribute('title') || ''));
      check(`${where}: each brief link says it can be absent and answer 404`, titles.length === 2 && titles.every((t) => t.includes('could not be written') && t.includes('404') && t.includes('first evening run')), titles);
      // the scorecard read honestly: the record's own sentences, verbatim, in order
      const reading = await page.locator('#record-card [data-scorecard-reading-sentence]').allTextContents();
      eq(`${where}: the scorecard reading prints the record's own sentences`, reading, full.scorecard_reading.sentences);
      eq(`${where}: and carries the block's status`, await page.evaluate(() => { const n = document.querySelector('#record-card [data-scorecard-reading]'); return n ? n.getAttribute('data-scorecard-reading') : null; }), full.scorecard_reading.status);
      // the go-live gate: the record's own sentence, and each criterion met or not
      const gate = full.run.go_live;
      eq(`${where}: the go-live gate names the record's state`, await page.evaluate(() => { const n = document.querySelector('#record-card [data-go-live]'); return n ? n.getAttribute('data-go-live') : null; }), gate.ready ? 'live' : 'paper');
      eq(`${where}: and prints its sentence`, await first(page, '#record-card [data-go-live-sentence]'), gate.sentence);
      const crit = await page.locator('#record-card [data-go-live-criterion]').evaluateAll((nodes) => nodes.map((n) => [n.getAttribute('data-go-live-criterion'), n.textContent]));
      eq(`${where}: and each criterion, met or not, with its detail`, crit, gate.criteria.map((c) => [c.key, c.key.replace(/_/g, ' ') + ': ' + (c.met ? 'met' : 'not met') + ' (' + c.detail + ')']));
      check(`${where}: nothing scrolls sideways`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await within(page, '#record-card [data-scorecard-method]', (n) => { n.open = true; }, null);
        await page.screenshot({ path: path.join(shotsDir, `pagetext-record-${width}-${theme}.png`), fullPage: true });
      }
      eq(`${where}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
  // the window is the record's own number, and a record that archives none names none
  for (const [name, mutate, want] of [['window-45', (d) => { d.rules.intraday.window_minutes = 45; }, 'inside the plan’s first 45 minutes (rule '], ['no-window', (d) => { delete d.rules.intraday.window_minutes; }, 'inside the plan’s entry window (rule ']]) {
    const d = clone(full); mutate(d);
    const rw = routed('record-' + name, d);
    const { page, context } = await open(browser, base, rw.url, NOW, 1280, { beforeLoad: rw.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      check(`record ${name}: the minute window is the record's own`, (await first(page, '#record-card [data-scorecard-prices]')).includes(want + full.rules.record.intraday_fill + ')'), await first(page, '#record-card [data-scorecard-prices]'));
    } finally { await context.close(); }
  }
  // a record from before the reading says so, and one whose reading cannot be read says that
  for (const [name, mutate, state, words] of [
    ['reading-absent', (d) => { delete d.scorecard_reading; }, 'absent', 'This record is from before the scorecard reading'],
    ['reading-unreadable', (d) => { d.scorecard_reading.sentences = 'not a list'; }, 'unreadable', 'This record’s scorecard reading could not be read.']]) {
    const d = clone(full); mutate(d);
    const rr = routed('record-' + name, d);
    const { page, context } = await open(browser, base, rr.url, NOW, 1280, { beforeLoad: rr.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      eq(`record ${name}: the reading's state`, await page.evaluate(() => { const n = document.querySelector('#record-card [data-scorecard-reading]'); return n ? n.getAttribute('data-scorecard-reading') : null; }), state);
      check(`record ${name}: says so in its own words`, ((await page.locator('#record-card [data-scorecard-reading] .sc-note').allTextContents())[0] || '').startsWith(words), await page.locator('#record-card [data-scorecard-reading] .sc-note').allTextContents());
      eq(`record ${name}: and prints no sentence of a reading`, await page.locator('#record-card [data-scorecard-reading-sentence]').count(), 0);
    } finally { await context.close(); }
  }
  // a record from before the gate is paper only, and one whose gate cannot be read says that
  for (const [name, mutate, state, words] of [
    ['gate-absent', (d) => { delete d.run.go_live; }, 'absent', 'This record is from before the go-live gate'],
    ['gate-unreadable', (d) => { d.run.go_live.criteria = 'not a list'; }, 'unreadable', 'This record’s go-live gate could not be read'],
    ['gate-no-criteria', (d) => { d.run.go_live.criteria = []; }, 'unreadable', 'This record’s go-live gate could not be read'],
    ['gate-no-sentence', (d) => { d.run.go_live.sentence = 5; }, 'unreadable', 'This record’s go-live gate could not be read']]) {
    const d = clone(full); mutate(d);
    const rg = routed('record-' + name, d);
    const { page, context } = await open(browser, base, rg.url, NOW, 1280, { beforeLoad: rg.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      eq(`record ${name}: the gate's state`, await page.evaluate(() => { const n = document.querySelector('#record-card [data-go-live]'); return n ? n.getAttribute('data-go-live') : null; }), state);
      check(`record ${name}: says so in its own words`, ((await page.locator('#record-card [data-go-live] .sc-note').allTextContents())[0] || '').startsWith(words), await page.locator('#record-card [data-go-live] .sc-note').allTextContents());
      eq(`record ${name}: and names no criterion`, await page.locator('#record-card [data-go-live-criterion]').count(), 0);
    } finally { await context.close(); }
  }
  // a gate that holds is shown live, its own sentence printed, every criterion met
  {
    const d = clone(full);
    d.run.go_live.ready = true; d.run.go_live.reasons = [];
    d.run.go_live.criteria.forEach((c) => { c.met = true; });
    d.run.go_live.sentence = 'Live ready: every go-live condition holds; orders.json is no longer paper only.';
    const rg = routed('record-gate-live', d);
    const { page, context } = await open(browser, base, rg.url, NOW, 1280, { beforeLoad: rg.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      eq('record gate-live: the gate is shown live', await page.evaluate(() => { const n = document.querySelector('#record-card [data-go-live]'); return n ? n.getAttribute('data-go-live') : null; }), 'live');
      eq('record gate-live: and prints the record’s own sentence', await first(page, '#record-card [data-go-live-sentence]'), d.run.go_live.sentence);
    } finally { await context.close(); }
  }
  // only true is ready and only true is met: a truthy word is neither, and a row that is no criterion is left out
  {
    const d = clone(full);
    d.run.go_live.ready = 'yes';
    d.run.go_live.criteria[1].met = 'yes';
    d.run.go_live.criteria = [null, { met: true }].concat(d.run.go_live.criteria);
    const rg = routed('record-gate-truthy', d);
    const { page, context, errors } = await open(browser, base, rg.url, NOW, 1280, { beforeLoad: rg.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      eq('record gate-truthy: a ready that is not true is paper', await page.evaluate(() => { const n = document.querySelector('#record-card [data-go-live]'); return n ? n.getAttribute('data-go-live') : null; }), 'paper');
      const crit = await page.locator('#record-card [data-go-live-criterion]').evaluateAll((nodes) => nodes.map((n) => [n.getAttribute('data-go-live-criterion'), n.textContent]));
      eq('record gate-truthy: only the gate’s own criteria are listed', crit.map((c) => c[0]), full.run.go_live.criteria.map((c) => c.key));
      check('record gate-truthy: a met that is not true is not met', (crit[1] || [])[1] && crit[1][1].startsWith(full.run.go_live.criteria[1].key.replace(/_/g, ' ') + ': not met'), crit[1]);
      eq('record gate-truthy: no page errors', errors, []);
    } finally { await context.close(); }
  }
  // live as orders.json reads the block: a ready gate that still names a reason, or an unmet criterion, is paper
  for (const [name, mutate] of [
    ['gate-ready-with-a-reason', (g) => { g.ready = true; g.criteria.forEach((c) => { c.met = true; }); g.reasons = ['fidelity_protocol']; }],
    ['gate-ready-with-no-reasons-list', (g) => { g.ready = true; g.criteria.forEach((c) => { c.met = true; }); g.reasons = null; }],
    ['gate-ready-with-an-unmet-criterion', (g) => { g.ready = true; g.reasons = []; g.criteria.forEach((c, i) => { c.met = i !== 1; }); }],
    ['gate-ready-a-word-and-all-else-met', (g) => { g.ready = 'yes'; g.reasons = []; g.criteria.forEach((c) => { c.met = true; }); }]]) {
    const d = clone(full); mutate(d.run.go_live);
    const rg = routed('record-' + name, d);
    const { page, context, errors } = await open(browser, base, rg.url, NOW, 1280, { beforeLoad: rg.beforeLoad, reducedMotion: 'reduce' });
    try {
      await toView(page, 'record');
      eq(`record ${name}: the gate is paper`, await page.evaluate(() => { const n = document.querySelector('#record-card [data-go-live]'); return n ? n.getAttribute('data-go-live') : null; }), 'paper');
      eq(`record ${name}: no page errors`, errors, []);
    } finally { await context.close(); }
  }
  // a record from before the minute-bar rule names no minute bars
  const older = clone(full); delete older.rules.record.intraday_fill;
  const r = routed('record-older', older);
  const { page, context } = await open(browser, base, r.url, NOW, 1280, { beforeLoad: r.beforeLoad, reducedMotion: 'reduce' });
  try {
    await toView(page, 'record');
    check('record older: a record without the minute-bar rule names no minute bars', !(await first(page, '#record-card [data-scorecard-prices]')).includes('one-minute') && !(await first(page, '#hold-hint')).includes('one-minute') && (await first(page, '#hold-hint')).includes('walked from daily bars by the published ticket’s own rules.'), await first(page, '#hold-hint'));
  } finally { await context.close(); }
}

export async function checkPageText({ browser, base, open, check, eq, shotsDir, parts }) {
  console.log('-- page text: what the page says of the rules, held to the record and the modules');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const ctx = { browser, base, open, check, eq, full, shotsDir };
  // `parts` names the parts a mutant is judged by; the gate runs them all
  const suite = { veto, method, market, detail, deals, record: recordView };
  check('every part asked for is a part of this suite', !parts || parts.every((name) => name in suite), JSON.stringify(parts));
  for (const [name, run] of Object.entries(suite)) if (!parts || parts.includes(name)) await run(ctx);
}
