/* The Record view's historical findings (docs/app-findings.js over
   docs/historical-findings.json), read back through a real browser: the file
   is fetched only once the Record view is shown; the replay steps by button,
   index, hit column, keyboard and Play, and Play stops when the view is left;
   every number a caption, a pill, a table or a block prints is a field of the
   committed file at the precision the file carries it, held to that file read
   with fs and never to the page's prose; a stratum change recounts the dots
   and retables; a finger on a crowded spot is asked which night rather than
   given a neighbour; the phone stacks it with nothing sideways and no label
   cut; a routed copy of the file with one number changed prints that number
   (the page computes nothing); a 500, a wrong version and a malformed night
   each end in a sentence while the rest of the view stands; a session with no
   ratio breaks the line rather than drawing a zero; and the live record, which
   wears no demo note, renders it too. Judged against the JSON on disk, never
   against SCStock.findings. */
import { readFile } from 'node:fs/promises';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NOW = '2026-09-10T22:31:00Z';         // the fixtures' own instant
const LIVE_NOW = '2026-10-06T14:00:00Z';    // a Tuesday morning over the real 5 October record
const HOST = '#historical-evidence [data-findings]';
const ROOTSEL = '#historical-evidence [data-find-root]';
const settle = (p, ms) => p.waitForTimeout(ms || 80);
const txt = (p, sel) => p.locator(sel).first().innerText();
const tc = (p, sel) => p.locator(sel).first().textContent();
const attr = (p, sel, a) => p.locator(sel).first().getAttribute(a);
// the words the page uses for numbers, rebuilt here so a check never reads them off the page
const thousands = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const at = (iso) => new Date(iso + 'T12:00:00Z');
const shortDate = (iso) => at(iso).getUTCDate() + ' ' + MONTHS[at(iso).getUTCMonth()];
const dayWords = (iso) => DAYS[at(iso).getUTCDay()] + ' ' + shortDate(iso);
const signed = (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
const R2 = (v) => signed(v, 2) + 'R';   // a sum, a median, and every figure of the pasted backtest
const R3 = (v) => signed(v, 3) + 'R';   // the study's means, written at three places
const plural = (n, noun) => thousands(n) + ' ' + noun + (n === 1 ? '' : 's');
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const VERDICTS = ['red', 'yellow', 'green'];
const verdictCount = (v) => VERDICTS.filter((k) => v[k]).map((k) => thousands(v[k]) + ' ' + k).join(', ');
const WORDS = { admitted: 'A-quality', B: 'graded B', C: 'graded C', skip: 'graded skip', vetoed: 'vetoed', all: 'every burst' };
const stepOf = (p) => p.evaluate((s) => Number(document.querySelector(s).getAttribute('data-step')), ROOTSEL);
const nightOf = (p) => attr(p, ROOTSEL, 'data-night');
const ghosts = (p) => p.locator('#historical-evidence .ss-find__night.is-ghost').count();
const dots = (p) => p.locator('#historical-evidence .ss-find__r').count();
const pill = (p) => tc(p, '#historical-evidence g[data-pill] text');
const facts = (p) => txt(p, '#historical-evidence [data-find="facts"]');
const playWord = (p) => txt(p, '#historical-evidence [data-find="play"]');
const sideways = (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
const rows = (p, sel) => p.locator(sel + ' tbody tr').evaluateAll((trs) => trs.map((tr) => Array.from(tr.querySelectorAll('td')).map((td) => td.textContent)));
const svgFits = (p) => p.evaluate(() => {
  const s = document.querySelector('#historical-evidence .ss-find__svg'), c = document.querySelector('#historical-evidence .ss-find__chart');
  return !!s && Math.abs(+s.getAttribute('width') - c.clientWidth) <= 2 && Math.abs(s.getBoundingClientRect().height - +s.getAttribute('height')) <= 2;
});
// every text of the chart inside the chart, and no two date labels touching
const labelsFit = (p) => p.evaluate(() => {
  const svg = document.querySelector('#historical-evidence .ss-find__svg'), s = svg.getBoundingClientRect();
  const out = Array.from(svg.querySelectorAll('text')).filter((t) => { const r = t.getBoundingClientRect(); return r.right > s.right + 1 || r.left < s.left - 1 || r.right > innerWidth || r.left < 0; }).map((t) => t.textContent);
  const dates = Array.from(svg.querySelectorAll('text.ss-find__date')).map((t) => t.getBoundingClientRect()).sort((a, b) => a.left - b.left);
  const touching = dates.filter((r, i) => i > 0 && r.left < dates[i - 1].right + 2).length;
  return { out, touching };
});
// waiting -> loading -> ready | error; then, when ready, the svg the ResizeObserver may draw a frame later
async function ready(p) {
  await p.waitForFunction((sel) => { const h = document.querySelector(sel); return h && (h.dataset.findings === 'ready' || h.dataset.findings === 'error'); }, HOST, { timeout: 15000 });
  const state = await attr(p, HOST, 'data-findings');
  if (state === 'ready') await p.waitForSelector('#historical-evidence .ss-find__svg', { timeout: 5000 });
  await settle(p, 120);
  return state;
}

export async function checkFindings({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- findings: the record night by night');
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const F = JSON.parse(await readFile(path.join(ROOT, 'docs', 'historical-findings.json'), 'utf8'));
  const N = F.nights.length, ns = F.nights_summary, th = F.market.thresholds, br = F.rules.breadth;
  const hold = String(F.rules.record.open_plan_sessions);
  const fast = (page) => page.addInitScript(() => { window.SCStock = Object.assign(window.SCStock || {}, { findingsInterval: 250 }); });
  const load = (dataUrl, width, extras) => open(browser, base, dataUrl, extras && extras.now || NOW, width,
    Object.assign({ lens: 'all', hash: '#/record', reducedMotion: 'reduce', beforeLoad: fast }, extras || {}));
  const FULL = '/tests/fixtures/page/full.json';

  // ---- 0. the files are fetched when the Record view is shown, never on another route
  const asked = [];
  const z = await load(FULL, 1280, { hash: '#/explore', beforeLoad: async (page) => { await fast(page); page.on('request', (r) => asked.push(new URL(r.url()).pathname)); } });
  await settle(z.page, 600);
  eq('off the Record view neither historical file is fetched', asked.filter((u) => /historical-(findings|validation)\.json$/.test(u)), []);
  eq('and the replay waits', await attr(z.page, HOST, 'data-findings'), 'waiting');
  await z.page.evaluate(() => { location.hash = '#/record'; });
  eq('showing the Record view loads it', await ready(z.page), 'ready');
  eq('each file is fetched once', [asked.filter((u) => u.endsWith('/historical-findings.json')).length, asked.filter((u) => u.endsWith('/historical-validation.json')).length], [1, 1]);
  await z.page.evaluate(() => { location.hash = '#/method'; }); await settle(z.page, 150);
  await z.page.evaluate(() => { location.hash = '#/record'; }); await settle(z.page, 300);
  eq('returning to the view fetches nothing again and mounts one replay', [asked.filter((u) => u.endsWith('/historical-findings.json')).length, await z.page.locator(ROOTSEL).count()], [1, 1]);
  eq('lazy-load page errors', z.errors, []);
  await z.context.close();

  // ---- 1. the mount over the fixture page
  const f = await load(FULL, 1280);
  const p = f.page;
  eq('the replay is ready on the Record view', await ready(p), 'ready');
  eq('a fixture page says the replay reads the public findings', await p.locator(HOST + ' p[data-findings-demo]').count(), 1);
  eq('the replay has its own heading, under the section\'s', await p.evaluate(() => { const h = document.querySelector('#historical-evidence h3.ss-find__h'); const r = document.querySelector('#historical-evidence [data-find-root]'); return h && r.getAttribute('aria-labelledby') === h.id ? h.textContent : null; }), 'The record, night by night');
  eq('the index lists every night of the file', await p.locator('#historical-evidence ol.ss-find__index > li > button[data-find-night]').count(), N);
  check('the chart is drawn at its own column\'s width, not scaled into it', await svgFits(p));
  eq('the chart is one image for assistive technology', await p.locator(HOST + ' svg[role="img"][aria-labelledby]').count(), 1);
  eq('one mark group per published night', await p.locator('#historical-evidence .ss-find__night').count(), N);
  eq('every settled R of the A-quality stratum is a dot', await dots(p), sum(F.nights.map((n) => n.strata.admitted.r.length)));
  eq('every night after the first is a ghost on night 1', await ghosts(p), N - 1);
  eq('the pill names night 1', await attr(p, '#historical-evidence g[data-pill]', 'data-pill'), F.nights[0].session);
  eq('Back is refused on night 1', await attr(p, '#historical-evidence [data-find="back"]', 'aria-disabled'), 'true');
  eq('Next is offered on night 1', await attr(p, '#historical-evidence [data-find="next"]', 'aria-disabled'), 'false');
  eq('Back and Next refuse by aria, never by the disabled attribute', await p.locator('#historical-evidence [data-find="back"][disabled], #historical-evidence [data-find="next"][disabled]').count(), 0);
  eq('each control\'s visible word starts its accessible name', await p.locator('#historical-evidence .ss-find__controls button').evaluateAll((bs) => bs.every((b) => (b.getAttribute('aria-label') || b.textContent).startsWith(b.textContent))), true);
  eq('Play is a plain button that says what it will do', await attr(p, '#historical-evidence [data-find="play"]', 'aria-pressed'), null);
  eq('one live region, the count; the caption is not live', [await p.locator('#historical-evidence [data-find-root] [aria-live]').evaluateAll((e) => e.map((x) => x.dataset.find)), await attr(p, '#historical-evidence .ss-find__caption', 'aria-live')], [['count'], null]);
  check('on a desktop the index sits beside the stage and the caption under the stage', await p.evaluate(() => {
    const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect();
    return r('.ss-find__side').left >= r('.ss-find__stage').right - 1 && r('.ss-find__caption').top >= r('.ss-find__stage').bottom - 1;
  }));
  eq('on a desktop every chart label stays inside the chart and no two dates touch', await labelsFit(p), { out: [], touching: 0 });
  const lead = await txt(p, HOST + ' p[data-find="lead"]');
  check('the lead counts the nights, the verdicts, the tickets and the bursts from the file', lead.includes('Over the ' + plural(ns.nights, 'published night') + ' from ' + dayWords(ns.from) + ' to ' + dayWords(ns.through))
    && lead.includes('the gate said ' + verdictCount(ns.verdicts) + ' and published ' + plural(ns.tickets_published, 'ticket') + ' out of ' + plural(ns.bursts, 'burst') + ' scanned'), lead);
  check('the lead does not claim every burst was ticketed', !/ticketed every burst/.test(lead) && lead.includes('ran the production ticket rules over every burst'), lead);
  check('the lead precedes the replay', await p.evaluate(() => { const l = document.querySelector('#historical-evidence p[data-find="lead"]'), r = document.querySelector('#historical-evidence [data-find-root]'); return !!(l.compareDocumentPosition(r) & Node.DOCUMENT_POSITION_FOLLOWING); }));
  // the legend names a key for each verdict the nights carry and no other, every key round
  eq('the legend keys exactly the verdicts the nights carry', await p.locator('#historical-evidence [data-find="legend"] [data-find-key]').evaluateAll((e) => e.map((x) => x.dataset.findKey)), VERDICTS.filter((v) => ns.verdicts[v]));
  eq('every swatch in the legend is round, as the marks it names', await p.locator('#historical-evidence [data-find="legend"] i.is-swatch').evaluateAll((e) => e.every((i) => getComputedStyle(i).borderRadius === '50%' && i.getBoundingClientRect().width > 0)), true);
  const key = await txt(p, '#historical-evidence [data-find="regime-key"]');
  check('the key reads the ratio rule from the file: the red threshold, the yellow one, its size and grades', key.includes('under ' + th.ratio_10d_red.toFixed(1) + ' it says red, no new longs')
    && key.includes('under ' + th.ratio_10d_yellow.toFixed(1) + ' yellow, size × ' + br.size_multiplier.yellow + ', ' + F.rules.pipeline.yellow_grades.join(' and ') + ' only')
    && key.includes('green only when no other breadth rule fires'), key);
  const cursorAt = () => p.evaluate(() => document.querySelector('#historical-evidence g[data-cursor]').style.transform);
  const cursor1 = await cursorAt();

  // ---- 2. the step loop: every night's words are the file's
  for (let k = 0; k < N; k++) {
    const nt = F.nights[k], a = nt.strata.admitted, st = a.settled, bk = a.buckets;
    if (k > 0) { await p.locator('#historical-evidence [data-find="next"]').click(); await settle(p); }
    const tag = `night ${k + 1}`;
    eq(`${tag}: the root names the session and the step`, [await nightOf(p), await attr(p, ROOTSEL, 'data-step')], [nt.session, String(k + 1)]);
    eq(`${tag}: is current in the index`, await attr(p, '#historical-evidence [data-find-night][aria-current="step"]', 'data-find-night'), nt.session);
    eq(`${tag}: its marks are current and the later nights are ghosts`, [await p.locator('#historical-evidence .ss-find__night.is-current').evaluateAll((e) => e.map((g) => g.dataset.night)), await ghosts(p)], [[nt.session], N - 1 - k]);
    const pl = await pill(p);
    eq(`${tag}: the count is one line naming the night and its outcome`, await txt(p, '#historical-evidence [data-find="count"]'), `Night ${k + 1} of ${N} · ${shortDate(nt.session)} · ${nt.regime.verdict} · ${pl}`);
    eq(`${tag}: the title carries the day, the verdict and the ratio`, await txt(p, '#historical-evidence [data-find="title"]'), dayWords(nt.session) + ' · ' + nt.regime.verdict + ' · ratio ' + nt.regime.ratio_10d.toFixed(2));
    const text = await txt(p, '#historical-evidence [data-find="text"]');
    check(`${tag}: the text counts the bursts, the checklist's A-quality, the vetoes and the tickets published`, text.includes('The scan found ' + plural(nt.bursts, 'burst') + '. The checklist graded ' + thousands(nt.a_quality.mechanical) + ' of them A-quality and vetoed ' + thousands(nt.vetoed) + '.')
      && text.includes('It published ' + plural(nt.tickets_published, 'ticket') + '.'), text);
    const reader = nt.reads.done
      ? 'The chart reader gave a usable read on ' + thousands(nt.reads.done) + ' of ' + plural(nt.reads.requested, 'requested name') + '; after it, ' + thousands(nt.a_quality.final) + ' stood at A-quality'
      : 'The chart reader gave no usable read on any of the ' + plural(nt.reads.requested, 'requested name') + ' that night; every grade is the checklist’s.';
    check(`${tag}: the reader's sentence is its usable reads and the counted A-quality after it`, text.includes(reader), [reader, text]);
    const fx = await facts(p);
    check(`${tag}: the facts count the stratum's bursts and the tickets the rules wrote`, fx.includes('of ' + plural(a.rows, 'A-quality burst') + ' the rules wrote ' + plural(a.tickets, 'ticket') + ' at full size'), fx);
    if (st.n > 0) {
      check(`${tag}: the facts print the wins, the sum at two places and the mean at three`, fx.includes(thousands(st.wins) + ' won, ' + thousands(st.losses) + ' lost, ' + thousands(st.breakeven) + ' even')
        && fx.includes(R2(st.sum_r) + ' in all, ' + R3(st.mean_r) + ' per settled ticket, median ' + R2(st.median_r)), fx);
      eq(`${tag}: the pill prints the mean as the file writes it and the settled count`, pl, R3(st.mean_r) + ' · ' + thousands(st.n) + ' settled');
      eq(`${tag}: "so far" only on a night still inside its hold`, fx.includes(thousands(st.n) + ' settled so far'), !nt.complete);
    } else {
      check(`${tag}: nothing settled is said so`, fx.includes('none settled yet') && !fx.includes(' won,'), fx);
      eq(`${tag}: the pill counts the pending tickets`, pl, bk.pending ? plural(bk.pending, 'ticket') + ' pending' : 'nothing settled');
    }
    eq(`${tag}: pending and open are told apart, each from its own bucket`, [fx.includes(thousands(bk.pending) + ' pending'), fx.includes(thousands(bk.open) + ' still open')], [!!bk.pending, !!bk.open]);
    eq(`${tag}: the bursts without a ticket are counted by cause`, [fx.includes(thousands(bk.no_ticket) + ' the rules would not write a ticket for'), fx.includes(thousands(bk.basis_mismatch) + ' set aside because the bars do not reproduce')], [!!bk.no_ticket, !!bk.basis_mismatch]);
    eq(`${tag}: an unfinished hold is said so, a finished one is not`, fx.includes('The ' + hold + '-session hold runs through ' + dayWords(nt.horizon)), !nt.complete);
    const fr = nt.first_read && nt.first_read.admitted;
    eq(`${tag}: an earlier read is quoted only where the file carries one`, fx.includes('The first read, with records through'), !!(fr && fr.n));
    if (fr && fr.n) {
      eq(`${tag}: the first read says it came before the hold ended only where it did`, fx.includes('before every ticket had had its ' + hold + ' sessions'), !nt.first_read.horizon_passed);
      check(`${tag}: the first read quotes the file's first mean at three places`, fx.includes(R3(fr.mean_r) + ' per settled ticket over ' + thousands(fr.n)), fx);
    }
    eq(`${tag}: the eyebrow says whether the hold is complete`, await txt(p, '#historical-evidence [data-find="eyebrow"]'), 'night ' + (k + 1) + ' of ' + N + ' · ' + nt.phase + ' · ' + (nt.complete ? hold + ' sessions complete' : 'inside its hold'));
    if (k === 1) {
      check('the cursor moved between night 1 and night 2', (await cursorAt()) !== cursor1 && /translateX\(/.test(await cursorAt()), [cursor1, await cursorAt()]);
      check('under reduced motion a step is not animated', await p.evaluate(() => !document.querySelector('#historical-evidence [data-find-root]').classList.contains('is-animated') && !/transform/.test(getComputedStyle(document.querySelector('#historical-evidence g[data-cursor]')).transitionProperty)));
      eq('the current night stands out in the index', await p.evaluate(() => { const b = (s) => getComputedStyle(document.querySelector('#historical-evidence [data-find-night]' + s)).backgroundColor; return b('[aria-current="step"]') !== b('[aria-current="false"]'); }), true);
    }
  }
  eq('Next is refused on the last night', await attr(p, '#historical-evidence [data-find="next"]', 'aria-disabled'), 'true');
  eq('Back is offered on the last night', await attr(p, '#historical-evidence [data-find="back"]', 'aria-disabled'), 'false');

  // ---- 5. the chart's own words, and the dots of a sampled night
  eq('the two reference lines are named at the axis by their thresholds', [await tc(p, '#historical-evidence text[data-ref-label="red"]'), await tc(p, '#historical-evidence text[data-ref-label="yellow"]')], [th.ratio_10d_red.toFixed(1), th.ratio_10d_yellow.toFixed(1)]);
  eq('the reference lines are drawn once each, and no line claims green', await p.locator('#historical-evidence line[data-ref]').evaluateAll((e) => e.map((l) => l.dataset.ref).sort()), ['red', 'yellow']);
  eq('two washes: under the red line and between the lines', await p.locator('#historical-evidence rect.ss-find__wash').count(), 2);
  const bracket = await tc(p, '#historical-evidence text[data-bracket-label="backtest"]');
  check('the backtest bracket counts the exact lookback\'s sessions', bracket.includes(plural(F.backtest.lookback_260.evaluated.count, 'session')) && (await p.locator('#historical-evidence path[data-bracket="backtest"]').count()) === 1, bracket);
  const ticks = await p.locator('#historical-evidence text[data-r-tick]').evaluateAll((e) => e.map((t) => ({ y: +t.getAttribute('y'), text: t.textContent, v: t.dataset.rTick })));
  check('the outcome axis is labelled in real multiples with zero among them', ticks.some((t) => t.text === '0R') && ticks.every((t) => /^[+−]?\d+R$/.test(t.text)), JSON.stringify(ticks));
  check('no two outcome ticks overlap', ticks.slice().sort((a, b) => a.y - b.y).every((t, i, s) => i === 0 || t.y - s[i - 1].y >= 11), JSON.stringify(ticks));
  eq('the first published night is said to follow sessions with no scan', await p.locator('#historical-evidence text[data-note="before"]').count(), F.market.sessions[0].date < F.nights[0].session ? 1 : 0);
  eq('every session has a hit column', await p.locator('#historical-evidence rect.ss-find__hit[data-hit][data-i]').count(), F.market.sessions.length);
  eq('the date axis is labelled', (await p.locator('#historical-evidence text.ss-find__date').count()) >= 3, true);
  const busiest = F.nights.reduce((b, n, k) => n.strata.admitted.r.length > F.nights[b].strata.admitted.r.length ? k : b, 0);
  for (const k of [...new Set([0, Math.floor(N / 2), busiest])]) {
    const nt = F.nights[k];
    await p.locator(`#historical-evidence [data-find-night="${nt.session}"]`).click(); await settle(p);
    const drawn = await p.locator('#historical-evidence .ss-find__night.is-current .ss-find__r').evaluateAll((e) => e.map((c) => Number(c.dataset.r)));
    const list = nt.strata.admitted.r;
    check(`night ${k + 1}: every drawn R is one the file lists, and all of them`, drawn.length === list.length && drawn.every((v) => list.includes(v)), JSON.stringify([drawn, list]));
    eq(`night ${k + 1}: the mean mark carries the file's mean`, await attr(p, '#historical-evidence .ss-find__night.is-current .ss-find__mean', 'data-mean'), nt.strata.admitted.settled.mean_r === null ? 'none' : String(nt.strata.admitted.settled.mean_r));
  }

  // ---- 3. the stratum control recounts the dots and retables
  const kMid = 5, mid = F.nights[kMid];
  await p.locator(`#historical-evidence [data-find-night="${mid.session}"]`).click(); await settle(p);
  const pressed = () => p.locator('#historical-evidence button[data-find-stratum][aria-pressed="true"]').evaluateAll((e) => e.map((b) => b.dataset.findStratum));
  eq('the control opens on the A-quality stratum', [await attr(p, ROOTSEL, 'data-stratum'), await pressed()], ['admitted', ['admitted']]);
  eq('the control is a captioned group', await p.evaluate(() => { const g = document.querySelector('#historical-evidence .sc-field--group'); const l = g && g.querySelector('.sc-field__label'); return l && l.textContent; }), 'tickets');
  const nightsTable = '#historical-evidence details[data-find="table-nights"]';
  for (const [s, block, noun] of [['all', (n) => n.all, 'burst'], ['B', (n) => n.strata.B, 'graded B burst']]) {
    await p.locator(`#historical-evidence [data-find-stratum="${s}"]`).click(); await settle(p);
    eq(`stratum ${s}: the root and the pressed tab move`, [await attr(p, ROOTSEL, 'data-stratum'), await pressed()], [s, [s]]);
    eq(`stratum ${s}: the step is kept`, await stepOf(p), kMid + 1);
    eq(`stratum ${s}: every settled R of the stratum is a dot`, await dots(p), sum(F.nights.map((n) => block(n).r.length)));
    const b = block(mid), fx = await facts(p);
    check(`stratum ${s}: the facts name the stratum and count its bursts and tickets`, fx.includes('of ' + plural(b.rows, noun) + ' the rules wrote ' + plural(b.tickets, 'ticket') + ' at full size'), fx);
    eq(`stratum ${s}: the pill prints the stratum's mean`, await pill(p), R3(b.settled.mean_r) + ' · ' + thousands(b.settled.n) + ' settled');
    await p.locator(nightsTable + ' > summary').click(); await settle(p);
    eq(`stratum ${s}: the nights table opens with every night`, [await p.locator(nightsTable).evaluate((d) => d.open), (await rows(p, nightsTable)).length], [true, N]);
    const row = (await rows(p, nightsTable))[kMid];
    eq(`stratum ${s}: the current night's row counts the stratum's bursts, tickets, settled, sum and mean`, [row[7], row[8], row[9], row[13], row[14]],
      [thousands(b.rows), thousands(b.tickets), thousands(b.settled.n), signed(b.settled.sum_r, 2), signed(b.settled.mean_r, 3)]);
    eq(`stratum ${s}: and the night's counted A-quality before and after the reader`, [row[4], row[5]], [thousands(mid.a_quality.mechanical), thousands(mid.a_quality.final)]);
    await p.locator(nightsTable + ' > summary').click(); await settle(p);
  }
  await p.locator('#historical-evidence [data-find-stratum="admitted"]').click(); await settle(p);
  eq('back to A-quality the dots are recounted', [await attr(p, ROOTSEL, 'data-stratum'), await dots(p)], ['admitted', sum(F.nights.map((n) => n.strata.admitted.r.length))]);
  eq('both tables are named, focusable regions, as every twin in the app', await p.locator('#historical-evidence .ss-find__tables .sc-table-scroll').evaluateAll((e) => e.map((x) => [x.getAttribute('tabindex'), x.getAttribute('role'), !!x.getAttribute('aria-label')])), [['0', 'region', true], ['0', 'region', true]]);

  // ---- 4. the market table: every session the records know
  const marketTable = '#historical-evidence details[data-find="table-market"]';
  await p.locator(marketTable + ' > summary').click(); await settle(p);
  const mrows = await rows(p, marketTable);
  eq('the market table carries every session', mrows.length, F.market.sessions.length);
  eq('the first row prints the first session\'s ratio', mrows[0][3], F.market.sessions[0].ratio_10d.toFixed(2));
  eq('publication rows and history rows say where they were read from', [mrows.filter((r) => r[5].includes('its own publication')).length, mrows.filter((r) => r[5].includes('the history of')).length],
    [F.market.sessions.filter((s) => s.basis === 'publication').length, F.market.sessions.filter((s) => s.basis === 'history').length]);
  eq('a session a later history re-read says so', mrows.filter((r) => r[5].includes('a later history reads')).length, F.market.sessions.filter((s) => typeof s.later_ratio_10d === 'number').length);
  eq('a session with no publication says so', mrows.filter((r) => r[4] === 'no publication').length, F.market.sessions.filter((s) => !s.verdict).length);

  // ---- 6. a hit column: hover names the session, a mouse click takes the nearest published night
  const target = F.nights[3], ts = F.market.sessions.find((s) => s.date === target.session);
  await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p);
  await p.locator(`#historical-evidence rect[data-hit="${target.session}"]`).hover(); await settle(p, 150);
  const tip = p.locator('#historical-evidence .ss-find__chart .sc-tooltip.is-on');
  eq('hovering a column shows the tooltip', await tip.isVisible(), true);
  const tipText = await tip.innerText();
  check('the tooltip prints the session\'s ratio, counts and verdict', tipText.includes(ts.ratio_10d.toFixed(2)) && tipText.includes(thousands(ts.up4) + ' / ' + thousands(ts.down4)) && tipText.includes('verdict ' + ts.verdict), tipText);
  await p.locator(`#historical-evidence rect[data-hit="${target.session}"]`).click(); await settle(p);
  eq('clicking a published night\'s column makes it current', await nightOf(p), target.session);
  const far = F.market.sessions.find((s) => s.basis === 'history');
  await p.locator(`#historical-evidence rect[data-hit="${far.date}"]`).hover(); await settle(p, 150);
  check('a session with no publication says so in its tooltip', (await tip.innerText()).includes('no publication'), await tip.innerText());
  await p.locator(`#historical-evidence rect[data-hit="${far.date}"]`).click(); await settle(p);
  eq('clicking a session far from every published night moves nothing', await nightOf(p), target.session);
  eq('a mouse is never asked to choose', await p.locator('#historical-evidence [data-find="pick"]').count(), 0);
  await p.mouse.move(0, 0); await settle(p, 150);
  eq('leaving the chart hides the tooltip', await tip.count(), 0);

  // ---- 7. the keyboard on the stage, and Play
  await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p);
  await p.locator('#historical-evidence .ss-find__stage').focus();
  await p.keyboard.press('ArrowRight'); await settle(p);
  eq('ArrowRight steps forward', await stepOf(p), 2);
  await p.keyboard.press('ArrowLeft'); await settle(p);
  eq('ArrowLeft steps back', await stepOf(p), 1);
  await p.keyboard.press('End'); await settle(p);
  eq('End goes to the last night', await stepOf(p), N);
  await p.keyboard.press('Home'); await settle(p);
  eq('Home goes to the first', await stepOf(p), 1);
  await p.keyboard.press(' '); await settle(p, 650);
  check('Space plays from the stage', (await playWord(p)) === 'Pause' && (await stepOf(p)) >= 2, await stepOf(p));
  await p.locator('#historical-evidence [data-find="play"]').click();
  const held = await stepOf(p); await settle(p, 600);
  eq('Pause holds the night', await stepOf(p), held);
  eq('Pause reads Play again', await playWord(p), 'Play');
  await p.locator('#historical-evidence [data-find="next"]').focus();
  await p.keyboard.press(' '); await settle(p);
  eq('Space on the Next button steps rather than plays', [await stepOf(p), await playWord(p)], [held + 1, 'Play']);
  await p.locator('#historical-evidence [data-find-night]').last().click(); await settle(p);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 120);
  eq('Play from the last night starts over', await stepOf(p), 1);
  // leaving the view stops it: the stepping is for a reader who is watching
  await p.evaluate(() => { location.hash = '#/method'; }); await settle(p, 900);
  const away = await stepOf(p);
  await settle(p, 700);
  eq('off the view Play has stopped and the night holds', [await stepOf(p), await playWord(p)], [away, 'Play']);
  check('it stopped within a step of leaving', away <= 3, away);
  await p.evaluate(() => { location.hash = '#/record'; }); await settle(p, 300);

  // ---- 8. the blocks under the replay: the backtest, run 6, the reading
  const L = F.backtest.lookback_130, X = F.backtest.lookback_260, prod = L.gates.production, cf = L.gates.no_regime_gate;
  const strip = await txt(p, '#historical-evidence dl[data-find="backtest-strip"]');
  eq('the backtest strip is four cells', await p.locator('#historical-evidence dl[data-find="backtest-strip"] .sc-stat').count(), 4);
  check('the strip prints the sessions, the tickets and the net R as the summary wrote them', strip.includes(thousands(L.evaluated.count)) && strip.includes(thousands(prod.tickets)) && strip.includes(R2(prod.settled.sum_r)) && strip.includes(plural(prod.settled.n, 'settled ticket')), strip);
  check('the strip counts the nights by regime, green included', strip.includes(thousands(L.regimes.verdicts.yellow || 0)) && strip.includes(thousands(L.regimes.verdicts.red || 0) + ' red · ' + thousands(L.regimes.verdicts.green || 0) + ' green'), strip);
  eq('a figure in the strip never breaks inside itself', await p.locator('#historical-evidence dl[data-find="backtest-strip"] .sc-stat__value').evaluateAll((e) => e.every((d) => d.getClientRects().length === 1 && d.getBoundingClientRect().height < 2 * parseFloat(getComputedStyle(d).fontSize))), true);
  const rates = await txt(p, '#historical-evidence p[data-find="backtest-rates"]');
  check('the rates line prints the win rate, the mean and the median the summary read', prod.settled.readable === true && rates.includes('Win rate ' + Math.round(prod.settled.win_rate * 100) + '%') && rates.includes('mean ' + R2(prod.settled.avg_r)) && rates.includes('median ' + R2(prod.settled.median_r)), rates);
  check('SPY at the two places the summary printed it', rates.includes('SPY ' + signed(prod.settled.spy_avg_pct, 2) + '%'), rates);
  check('and the equivalence the shortened lookback passed', rates.includes('equivalence ' + L.lookback.equivalence.status) && rates.includes(plural(L.lookback.equivalence.differences, 'difference')), rates);
  const brows = await rows(p, '#historical-evidence [data-find="backtest-table"]');
  eq('the backtest table has the two blocks, their splits and the exact lookback', brows.length, 2 + Object.keys(cf.by_regime).length + Object.keys(cf.by_grade).length + 2);
  eq('the production row prints its tickets and its sum', [brows[0][0], brows[0][1], brows[0][4]], ['production', thousands(prod.tickets), signed(prod.settled.sum_r, 2)]);
  eq('the counterfactual row is named the gate removed, and prints its sum', [brows[1][0], brows[1][4]], ['gate removed', signed(cf.settled.sum_r, 2)]);
  check('a split row prints its own numbers and a dash for the breakeven the summary does not carry', Object.keys(cf.by_regime).sort().every((k, i) => brows[2 + i][0] === 'gate removed, ' + k + ' nights' && brows[2 + i][4] === signed(cf.by_regime[k].sum_r, 2) && brows[2 + i][3].endsWith(' / —')), JSON.stringify(brows.slice(2, 4)));
  const exact = brows[brows.length - 2];
  check('the exact-lookback row prints a dash where the summary read no rate', X.gates.production.settled.avg_r === null && exact[0] === plural(X.evaluated.count, 'session') + ': production' && exact[5] === '—' && exact[7] === '—' && exact[4] === signed(X.gates.production.settled.sum_r, 2), JSON.stringify(exact));
  eq('a row label is not shredded: the first column keeps a readable width', await p.locator('#historical-evidence [data-find="backtest-table"] tbody tr:first-child td:first-child').evaluate((td) => td.getBoundingClientRect().width >= 9 * parseFloat(getComputedStyle(td).fontSize)), true);
  const source = await txt(p, '#historical-evidence p[data-find="backtest-source"]');
  check('the source line names both summaries by their digests', source.includes(L.source.sha256.slice(0, 12)) && source.includes(X.source.sha256.slice(0, 12)), source);
  await p.locator('#historical-evidence details[data-find="backtest-limits"] > summary').click(); await settle(p);
  eq('the backtest\'s own limitations are printed as its summary lists them', await p.locator('#historical-evidence details[data-find="backtest-limits"] li').evaluateAll((e) => e.map((li) => li.textContent)), L.limitations);
  const days = Object.keys(F.run6.sessions).sort(), first = F.run6.sessions[days[0]];
  const r6 = await rows(p, '#historical-evidence [data-find="run6-table"]');
  eq('the run-6 table has one row per session', r6.length, days.length);
  check('the first row prints the published and the fresh ratio', r6[0][1].startsWith(first.original.ratio_10d.toFixed(2)) && r6[0][2] === first.policies.C.ratio_10d.toFixed(2) && r6[0][4].includes(first.policies.C.ratio_10d_bounds.map((v) => v.toFixed(2)).join(' to ')), JSON.stringify(r6[0]));
  const r6facts = await txt(p, '#historical-evidence p[data-find="run6-facts"]');
  check('the run-6 facts name every blocking stock, the download and each session\'s own partial count', F.run6.blocking_names.every((n) => r6facts.includes(n)) && r6facts.includes(thousands(F.run6.download.queries_completed) + ' of ' + thousands(F.run6.download.queries_total) + ' queries')
    && days.every((d) => r6facts.includes(thousands(F.run6.sessions[d].partial) + ' on ' + shortDate(d))), r6facts);
  eq('the run-6 table is named by its run number', await attr(p, '#historical-evidence [data-find="run6-table"]', 'aria-label'), 'Run ' + thousands(F.run6.public.run_number) + ' as a table');
  const readAs = await p.locator('#historical-evidence ul[data-find="read-as"] > li').evaluateAll((e) => e.map((li) => li.textContent));
  eq('the reading is four sentences', readAs.length, 4);
  const S = F.study.summary.strata;
  const pooled = Object.keys(WORDS).filter((s) => s !== 'all').map((s) => WORDS[s] + ' ' + R3(S[s].settled.mean_r) + ' over ' + thousands(S[s].settled.n)).join('; ');
  check('the pooled sentence counts the nights and prints every stratum\'s mean and count from the study block', readAs[0].startsWith('Pooled over the ' + plural(ns.nights, 'published night') + ' (' + verdictCount(ns.verdicts) + ') to ' + dayWords(F.study.newest_session) + ', ')
    && readAs[0].includes(': ' + pooled + '. '), [pooled, readAs[0]]);
  const allUnder = Object.keys(WORDS).filter((s) => s !== 'all').every((s) => S[s].settled.mean_r < 0);
  const positive = ns.admitted_positive_nights;
  eq('the count of positive A-quality nights is the file\'s own count of them', positive, F.nights.filter((n) => n.strata.admitted.settled.mean_r > 0).length);
  eq('the pooled sentence says whether every stratum is under zero, from the file', readAs[0].includes('Every stratum is under zero'), allUnder);
  eq('and counts the nights with a positive A-quality mean rather than asserting one', readAs[0].includes('though ' + thousands(positive) + ' of the nights had a positive A-quality mean'), allUnder && positive > 0);
  eq('only an all-red record says yellow and green are not in it', readAs[0].includes('not in this record, which has carried none'), VERDICTS.every((v) => v === 'red' || !ns.verdicts[v]));
  eq('every report is linked at its served path', await p.locator('#historical-evidence ul[data-find="reports"] a').evaluateAll((e) => e.map((a) => [a.getAttribute('href'), a.textContent])), F.reports.map((r) => [r.path.replace(/^docs\//, ''), r.title]));

  // ---- 9. nothing undefined, nothing open, no errors
  const all = await txt(p, '#historical-evidence');
  check('nothing in the section prints undefined or NaN', !/\bundefined\b|\bNaN\b/.test(all), (all.match(/.{0,40}\b(undefined|NaN)\b.{0,40}/) || [''])[0]);
  eq('the replay opens no dialog', await p.locator('dialog[open]').count(), 0);
  eq('the frozen cases of the 28 September review still follow the replay', await p.locator('#historical-evidence [data-study-case]').count(), 3);
  if (shotsDir) { await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p); await p.locator('#historical-evidence').screenshot({ path: path.join(shotsDir, 'findings-1280-dark.png') }); }
  eq('findings page errors', f.errors, []);
  await f.context.close();

  // ---- 10. phones, both themes: stacked, fitting, labels whole; a finger on a crowd is asked
  const crowded = F.nights.reduce((b, n, k) => (k > 0 && k < N - 1 && n.strata.admitted.r.length > F.nights[b].strata.admitted.r.length) ? k : b, 1);
  for (const width of [390, 320]) for (const theme of ['dark', 'light']) {
    const n = await load(FULL, width, { height: 844, theme, touch: true });
    const q = n.page, tag = `${width} ${theme}`;
    eq(`${tag}: the replay is ready`, await ready(q), 'ready');
    check(`${tag}: nothing scrolls sideways`, !(await sideways(q)));
    check(`${tag}: the chart fits its column`, await svgFits(q));
    check(`${tag}: the stage, the index and the caption stack`, await q.evaluate(() => {
      const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect();
      return r('.ss-find__side').top >= r('.ss-find__stage').bottom - 1 && r('.ss-find__caption').top >= r('.ss-find__side').bottom - 1;
    }));
    check(`${tag}: the tabs' caption sits over them, not beside them`, await q.evaluate(() => {
      const g = document.querySelector('#historical-evidence .ss-find__filter'), l = g.querySelector('.sc-field__label').getBoundingClientRect(), t = g.querySelector('.sc-tabs').getBoundingClientRect();
      return l.bottom <= t.top + 1;
    }));
    eq(`${tag}: every chart label is inside the chart and the screen, no two dates touch`, await labelsFit(q), { out: [], touching: 0 });
    eq(`${tag}: the reference lines keep their threshold labels`, [await tc(q, '#historical-evidence text[data-ref-label="red"]'), await tc(q, '#historical-evidence text[data-ref-label="yellow"]')], [th.ratio_10d_red.toFixed(1), th.ratio_10d_yellow.toFixed(1)]);
    await q.locator('#historical-evidence [data-find="next"]').click(); await settle(q);
    check(`${tag}: a step keeps the chart inside its column`, (await stepOf(q)) === 2 && !(await sideways(q)));
    // a finger on the crowded middle: the nights within reach are offered, nearest first, and none is taken
    const night = F.nights[crowded];
    await q.locator('#historical-evidence .ss-find__svg').evaluate((e) => e.scrollIntoView({ block: 'center' })); await settle(q, 150);
    const spot = await q.evaluate((s) => { const c = document.querySelector('#historical-evidence .ss-find__night[data-night="' + s + '"] .ss-find__mean'); const b = c.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; }, night.session);
    await q.touchscreen.tap(spot.x, spot.y); await settle(q, 200);
    const offered = await q.locator('#historical-evidence [data-find="pick"] [data-pick-night]').evaluateAll((e) => e.map((b) => b.dataset.pickNight));
    check(`${tag}: a tap on a crowd opens the chooser, the tapped night first`, offered.length > 1 && offered[0] === night.session, JSON.stringify(offered));
    eq(`${tag}: and chooses nothing until the reader does`, await stepOf(q), 2);
    eq(`${tag}: the chooser's first night has the focus`, await q.evaluate(() => document.activeElement && document.activeElement.dataset.pickNight), night.session);
    eq(`${tag}: the chooser's Close stays on one line`, await q.locator('#historical-evidence [data-find="pick"] [data-pick="close"]').evaluate((b) => b.getClientRects().length === 1 && b.getBoundingClientRect().height < 2.4 * parseFloat(getComputedStyle(b).fontSize)), true);
    const second = offered[1];
    await q.locator(`#historical-evidence [data-find="pick"] [data-pick-night="${second}"]`).click(); await settle(q);
    eq(`${tag}: choosing a night takes that night and closes the chooser`, [await nightOf(q), await q.locator('#historical-evidence [data-find="pick"]').count()], [second, 0]);
    await q.touchscreen.tap(spot.x, spot.y); await settle(q, 200);
    await q.keyboard.press('Escape'); await settle(q);
    eq(`${tag}: Escape closes it, the night unchanged, the focus back on the stage`, [await q.locator('#historical-evidence [data-find="pick"]').count(), await nightOf(q), await q.evaluate(() => document.activeElement && document.activeElement.classList.contains('ss-find__stage'))], [0, second, true]);
    if (shotsDir) await q.locator('#historical-evidence [data-find-root]').screenshot({ path: path.join(shotsDir, `findings-${width}-${theme}.png`) });
    eq(`${tag}: findings errors`, n.errors, []);
    await n.context.close();
  }
  const l = await load(FULL, 1280, { theme: 'light' });
  eq('light: the replay is ready', await ready(l.page), 'ready');
  if (shotsDir) await l.page.locator('#historical-evidence').screenshot({ path: path.join(shotsDir, 'findings-1280-light.png') });
  eq('findings light page errors', l.errors, []);
  await l.context.close();

  // ---- 11. motion on: a step animates the cursor
  const m = await load(FULL, 1280, { reducedMotion: 'no-preference' });
  eq('motion: the replay is ready', await ready(m.page), 'ready');
  await m.page.locator('#historical-evidence [data-find="next"]').click();
  check('a step with motion on marks the root animated and moves the cursor by a transition', await m.page.evaluate(() => document.querySelector('#historical-evidence [data-find-root]').classList.contains('is-animated') && /transform/.test(getComputedStyle(document.querySelector('#historical-evidence g[data-cursor]')).transitionProperty)));
  eq('motion page errors', m.errors, []);
  await m.context.close();

  // ---- 12. routed controls: the page prints the file, computes nothing, and refuses a file of another shape
  const routed = (body, status) => async (page) => {
    await fast(page);
    await page.route('**/historical-findings.json*', (route) => route.fulfill({ status: status || 200, contentType: 'application/json', body }));
  };
  const altered = structuredClone(F);
  altered.nights[0].strata.admitted.settled.sum_r = 123.45;
  altered.nights[0].a_quality.final = 4321;
  const a = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(altered)) });
  eq('altered file: the replay is ready', await ready(a.page), 'ready');
  const afx = await facts(a.page);
  check('a changed sum in the file is printed as given, so the page computes nothing', afx.includes('+123.45R in all') && !afx.includes(R2(F.nights[0].strata.admitted.settled.sum_r) + ' in all'), afx);
  check('and the mean beside it is still the file\'s own, not re-derived from the sum', (await pill(a.page)).includes(R3(F.nights[0].strata.admitted.settled.mean_r)), await pill(a.page));
  check('a changed count of A-quality after the reader is printed as given, not summed from grades', (await txt(a.page, '#historical-evidence [data-find="text"]')).includes('after it, ' + thousands(4321) + ' stood at A-quality'));
  eq('altered file errors', a.errors, []);
  await a.context.close();
  // a session with no ratio: the line breaks there and no zero is drawn
  const gap = structuredClone(F);
  const hole = gap.market.sessions.findIndex((s) => s.basis === 'history' && s.date > gap.market.sessions[0].date);
  gap.market.sessions[hole].ratio_10d = null;
  gap.nights[2].regime.ratio_10d = null;
  const g = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(gap)) });
  eq('gap file: the replay is ready', await ready(g.page), 'ready');
  eq('a session with no ratio breaks the line into two', await g.page.locator('#historical-evidence path.ss-find__line').evaluate((e) => (e.getAttribute('d').match(/M/g) || []).length), 2);
  eq('a night with no ratio has no dot rather than one at zero', await g.page.locator(`#historical-evidence .ss-find__night[data-night="${gap.nights[2].session}"] .ss-find__dot`).count(), 0);
  check('nothing in the chart is NaN', await g.page.evaluate(() => !/NaN/.test(document.querySelector('#historical-evidence .ss-find__svg').outerHTML)));
  eq('gap file errors', g.errors, []);
  await g.context.close();
  for (const [name, body, status, sentence] of [
    ['a 500', 'boom', 500, 'The validation findings did not load. Reload the page to try again.'],
    ['a wrong version', JSON.stringify(Object.assign(structuredClone(F), { version: 'historical-findings-v0' })), 200, 'Unknown findings version.'],
    ['a night without its B stratum', JSON.stringify((() => { const x = structuredClone(F); delete x.nights[2].strata.B; return x; })()), 200, 'A night of the findings lacks a stratum.'],
    ['a backtest without its gates', JSON.stringify((() => { const x = structuredClone(F); delete x.backtest.lookback_130.gates; return x; })()), 200, 'The findings carry no backtest.'],
    ['a body that is not JSON', '{"version": ', 200, 'The validation findings did not load. Reload the page to try again.'],
    // past the shape check, broken one block down: the replay that was drawn is taken away, never left half-built
    ['a backtest without its candidate counts', JSON.stringify((() => { const x = structuredClone(F); delete x.backtest.lookback_130.candidates; return x; })()), 200, 'The validation findings could not be read.'],
  ]) {
    const e = await load(FULL, 1280, { beforeLoad: routed(body, status) });
    eq(`${name}: the replay ends in its error state`, await ready(e.page), 'error');
    eq(`${name}: and says why in one sentence`, await txt(e.page, HOST + ' p[role="alert"]'), sentence);
    eq(`${name}: nothing half-drawn is left`, await e.page.locator(HOST + ' [data-find-root], ' + HOST + ' [data-find-block], ' + HOST + ' .ss-find__h').count(), 0);
    eq(`${name}: while the scorecard still renders`, (await txt(e.page, '#record-card')).includes('Published model plans'), true);
    eq(`${name}: and the open model plans and the frozen cases still render`, [await e.page.locator('#hold-rows > *').count(), await e.page.locator('#historical-evidence [data-study-case]').count()], [data.open_plans.length, 3]);
    eq(`${name}: the only error is the 500 this check served`, e.errors.filter((x) => !/500/.test(x)), []);
    await e.context.close();
  }

  // ---- 13. the live record wears no demo note
  const live = await load('/docs/data.json', 1280, { now: LIVE_NOW });
  eq('the live record is not a fixture', await live.page.getAttribute('html', 'data-ss-demo'), 'false');
  eq('live: the replay is ready', await ready(live.page), 'ready');
  eq('live: no demo note', await live.page.locator(HOST + ' p[data-findings-demo]').count(), 0);
  eq('live: every night is listed', await live.page.locator('#historical-evidence [data-find-night]').count(), N);
  eq('live findings errors', live.errors, []);
  await live.context.close();
}
