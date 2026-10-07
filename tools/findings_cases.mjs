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
   ratio breaks the line rather than drawing a zero; a stalled file ends in a
   sentence; routed variants drive every branch the committed file cannot (a
   yellow and a green night, a positive stratum, a readable confirmatory split,
   an unreadable backtest, other rule numbers); and the live record, which
   wears no demo note, renders it too. Judged against the JSON on disk, never
   against SCStock.findings. */
import { readFile } from 'node:fs/promises';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NOW = '2026-09-10T22:31:00Z';         // the fixtures' own instant
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
const sizeWords = (m) => m === 0 ? 'no new longs' : m === 1 ? 'full size' : 'size × ' + String(m);
const sentence = (parts) => parts.map((t) => /[.!?]$/.test(t) ? t : t + '.').join(' ');
// a settled block in words, the page's rule written again: a rate from the minimum, a count and a sum under it
const outcome = (st, min) => !st.n ? 'none settled' : st.n >= min ? R3(st.mean_r) + ' per settled ticket over ' + thousands(st.n)
  : thousands(st.n) + ' settled, ' + R2(st.sum_r) + ' in all, too few for a rate';
const pillOf = (b, min) => b.settled.mean_r === null ? (b.buckets.pending ? plural(b.buckets.pending, 'ticket') + ' pending' : 'nothing settled')
  : (b.settled.n >= min ? R3(b.settled.mean_r) : R2(b.settled.sum_r) + ' in all') + ' · ' + thousands(b.settled.n) + ' settled';
// what each stratum's counterfactual removed, and how its sentence opens
const REMOVED = {
  admitted: ['Gate removed, reader not run', 'A-quality burst', 'wrote', ''],
  B: ['Gate and grade removed, reader not run', 'graded B burst', 'would have written', ' had the grade not refused them'],
  vetoed: ['Gate and veto removed, reader not run', 'vetoed burst', 'would have written', ' had the veto not refused them'],
  all: ['Gate, grade and veto removed, reader not run', 'burst', 'would have written', ' had nothing refused them'],
};
const opening = (s, b) => REMOVED[s][0] + ': of ' + plural(b.rows, REMOVED[s][1]) + ' the plan rules ' + REMOVED[s][2] + ' ' + plural(b.tickets, 'ticket') + ' at full size' + REMOVED[s][3];
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
// the note before the first night: on a ground of its own, and over no night's mark
const noteClear = (p) => p.evaluate(() => {
  const note = document.querySelector('#historical-evidence text[data-note="before"]');
  if (!note) return { ground: true, under: 0 };
  const n = note.getBoundingClientRect(), g = note.previousElementSibling;
  const under = Array.from(document.querySelectorAll('#historical-evidence .ss-find__r, #historical-evidence .ss-find__mean, #historical-evidence .ss-find__dot'))
    .filter((c) => { const r = c.getBoundingClientRect(); return r.right > n.left && r.left < n.right && r.bottom > n.top && r.top < n.bottom; }).length;
  return { ground: !!g && g.classList.contains('ss-find__note-ground'), under };
});
// waiting -> loading -> ready | error; then, when ready, the svg the ResizeObserver may draw a frame later
async function ready(p) {
  await p.waitForFunction((sel) => { const h = document.querySelector(sel); return h && (h.dataset.findings === 'ready' || h.dataset.findings === 'error'); }, HOST, { timeout: 15000 });
  const state = await attr(p, HOST, 'data-findings');
  if (state === 'ready') await p.waitForSelector('#historical-evidence .ss-find__svg', { timeout: 5000 });
  await settle(p, 120);
  return state;
}

// the "Read it as" list against the file's reading block: the exploratory red nights by stratum
// and the minimum's rule, the confirmatory split from the study's own figure, the dated hold, the
// reader's two bounds, and the nights the reading leaves out
function readingHolds(F, readAs, eq, check, tag) {
  const rd = F.reading, ex = rd.phases.exploratory, co = rd.phases.confirmatory, ns = F.nights_summary, min = F.rules.record.scorecard_min_plans;
  const strata = Object.keys(WORDS).filter((s) => s !== 'all');
  const pooled = strata.map((s) => WORDS[s] + ' ' + (ex.strata[s].n >= min ? R3(ex.strata[s].mean_r) + ' over ' + thousands(ex.strata[s].n) : thousands(ex.strata[s].n) + ' settled, too few for a rate')).join('; ');
  const span = (b) => dayWords(b.from) + (b.from === b.through ? '' : ' to ' + dayWords(b.through));
  const readable = strata.filter((s) => ex.strata[s].n >= min);
  const allUnder = readable.length > 0 && readable.every((s) => ex.strata[s].mean_r < 0);
  check(tag + 'the exploratory sentence counts the red nights, dates the freeze and prints every stratum by the minimum\'s rule', readAs[0].startsWith('Exploratory: ' + (ex.red_nights === ex.nights
    ? 'the ' + plural(ex.nights, 'night') + ' from ' + span(ex) + ', every one red' : plural(ex.red_nights, 'red night') + ' of the ' + thousands(ex.nights) + ' from ' + span(ex)))
    && readAs[0].includes('frozen after ' + dayWords(rd.freeze)) && readAs[0].includes('The mean R per settled counterfactual ticket: ' + pooled + '. '), [pooled, readAs[0]]);
  eq(tag + 'the exploratory sentence says the refusals had value only when every readable stratum is under zero, and calls itself exploratory', [readAs[0].includes('on the nights the gate refused, its refusals had value in sum'),
    readAs[0].includes('Not every stratum is under zero'), readAs[0].endsWith('This is the exploratory reading, not evidence.')], [allUnder, !allUnder && readable.length > 0, readable.length > 0]);
  const cs = F.study.summary.phases.confirmatory, sc = cs.scorecard || {};
  check(tag + 'the confirmatory sentence counts its nights and reads the study\'s own split against its minimum', readAs[1].startsWith('Confirmatory: ' + plural(co.nights, 'night') + ' published after the freeze, ' + span(co))
    && readAs[1].includes('only from ' + plural(sc.min_read, 'settled ticket') + ': ') && readAs[1].includes(sc.readable ? 'the study’s confirmatory result is ' + R3(cs.settled.mean_r) + ' per settled ticket over ' + thousands(cs.settled.n) + '.'
      : thousands(cs.settled.n) + ' of the ' + thousands(sc.min_read) + ' have settled, so nothing confirmatory is readable yet.'), readAs[1]);
  eq(tag + 'a confirmatory night that was not red is named', readAs[1].includes(' of them were not red, so the gate published some of their tickets.') || readAs[1].includes(' of them was not red'), co.nights > co.red_nights);
  check(tag + 'the hold sentence is dated by the records the figures were read on', readAs[2].includes('Every figure here is as of the records through ' + dayWords(rd.as_of) + ', when ' + plural(ns.inside_hold, 'night') + ' still had tickets inside their hold'), readAs[2]);
  check(tag + 'the reader sentence keeps the backtest\'s caveat and claims no ceiling on the live policy\'s tickets', readAs[3].includes('its ticket set is not a superset of the live run’s') && !readAs[3].includes('no more tickets than any counterfactual'), readAs[3]);
  const other = ns.nights - ex.red_nights - co.red_nights;
  eq(tag + 'the last sentence counts the nights left out, or says every night was red', [readAs[4].includes('not red and'), readAs[4].includes('Every published night here was red')], [other > 0, other === 0]);
  if (other) check(tag + 'and counts them from the file', readAs[4].startsWith(plural(other, 'published night') + ' here '), readAs[4]);
}

export async function checkFindings({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- findings: the record night by night');
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const F = JSON.parse(await readFile(path.join(ROOT, 'docs', 'historical-findings.json'), 'utf8'));
  const N = F.nights.length, ns = F.nights_summary, th = F.market.thresholds, br = F.rules.breadth;
  const hold = String(F.rules.record.open_plan_sessions), min = F.rules.record.scorecard_min_plans;
  const asOf = F.study.newest_session, frozen = F.reading.phases.confirmatory.nights > 0;
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

  // ---- 0b. research last: the evidence follows the open model plans, so the old #hold anchor stays on them as it loads
  const h = await load(FULL, 1280, { hash: '#hold' });
  eq('the anchor route: the replay is ready', await ready(h.page), 'ready');
  eq('the evidence follows the open model plans in the Record view', await h.page.evaluate(() => !!(document.getElementById('hold').compareDocumentPosition(document.getElementById('historical-evidence')) & Node.DOCUMENT_POSITION_FOLLOWING)), true);
  check('a link to the open model plans still lands on them after the evidence has loaded', await h.page.evaluate(() => { const r = document.getElementById('hold').getBoundingClientRect(); return r.top >= -1 && r.top < innerHeight - 40; }), await h.page.evaluate(() => document.getElementById('hold').getBoundingClientRect().top));
  eq('anchor route errors', h.errors, []);
  await h.context.close();

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
  check('the lead does not claim every burst was ticketed, and says what each stratum removed', !/ticketed every burst/.test(lead)
    && lead.includes('ran the production plan rules over every burst, with the gate removed and the reader not run, and for the bursts graded B, C or skip or vetoed with the grade’s or the veto’s own refusal removed too'), lead);
  check('the lead dates its figures with the records they were read on', lead.includes('Its figures are as of the records through ' + dayWords(asOf) + '.'), lead);
  eq('each night in the index is named by its number, its day and its verdict, not a run of digits', await p.locator('#historical-evidence [data-find-night]').evaluateAll((e) => e.map((b) => b.getAttribute('aria-label'))),
    F.nights.map((n, k) => 'Night ' + (k + 1) + ', ' + dayWords(n.session) + ', ' + n.regime.verdict));
  check('the lead precedes the replay', await p.evaluate(() => { const l = document.querySelector('#historical-evidence p[data-find="lead"]'), r = document.querySelector('#historical-evidence [data-find-root]'); return !!(l.compareDocumentPosition(r) & Node.DOCUMENT_POSITION_FOLLOWING); }));
  // the legend names a key for each verdict the nights carry and no other, every key round
  eq('the legend keys exactly the verdicts the nights carry, the thin mean, and the freeze where a confirmatory night exists', await p.locator('#historical-evidence [data-find="legend"] [data-find-key]').evaluateAll((e) => e.map((x) => x.dataset.findKey)),
    VERDICTS.filter((v) => ns.verdicts[v]).concat(['thin']).concat(frozen ? ['freeze'] : []));
  check('the thin mean\'s key names the record\'s own minimum', (await txt(p, '#historical-evidence [data-find-key="thin"]')).includes('a mean of fewer than ' + plural(min, 'settled ticket') + ', not a rate'));
  if (frozen) {
    eq('the freeze is one dotted line, after the freeze session', await p.locator('#historical-evidence line[data-freeze]').evaluateAll((e) => e.map((l) => l.dataset.freeze)), [F.reading.freeze]);
    check('the freeze line sits between the last exploratory night and the first confirmatory one', await p.evaluate(([last, next]) => {
      const x = +document.querySelector('#historical-evidence line[data-freeze]').getAttribute('x1');
      const cx = (s) => +document.querySelector('#historical-evidence .ss-find__night[data-night="' + s + '"] .ss-find__dot').getAttribute('cx');
      return cx(last) < x && x < cx(next);
    }, [F.nights.filter((n) => n.phase === 'exploratory').pop().session, F.nights.find((n) => n.phase === 'confirmatory').session]));
    check('the freeze key and the chart\'s description name its date', (await txt(p, '#historical-evidence [data-find-key="freeze"]')).includes(shortDate(F.reading.freeze))
      && (await tc(p, '#historical-evidence .ss-find__svg desc')).includes('A dotted line after ' + dayWords(F.reading.freeze) + ' marks the study’s freeze'));
  }
  const desc = await tc(p, '#historical-evidence .ss-find__svg desc');
  check('the chart\'s description reads its rule numbers from the file and promises only what the tables carry', desc.includes('the ' + br.ratio_long_sessions + '-session ratio of stocks up ' + br.burst_pct + '% to stocks down')
    && desc.includes('drawn hollow where fewer than ' + min + ' settled') && desc.includes('every settled R included'), desc);
  eq('the chart is titled for what it draws, the ratio the records carry', await tc(p, '#historical-evidence .ss-find__svg title'), 'The breadth ratio the records carry, and what each night’s tickets did');
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
    check(`${tag}: the gate's verdict is quoted with every reason the record gave`, text.includes('The market gate said ' + nt.regime.verdict + ': ' + sentence(nt.regime.reasons) + ' It published'), [nt.regime.reasons, text]);
    // the market line: the chip is the verdict, the size words follow the multiplier, and the counts are the night's own, in order
    const first = p.locator('#historical-evidence [data-find="facts"] > li').first();
    eq(`${tag}: the market line's chip is the night's verdict`, await first.locator('.sc-chip').textContent(), nt.regime.verdict);
    eq(`${tag}: the market line is the night's size, its counts up and down on the day and over ten, and its ratio`, await first.textContent(),
      nt.regime.verdict + ' ' + sizeWords(nt.regime.size_multiplier) + ' · ' + thousands(nt.regime.up4) + ' up ' + br.burst_pct + '% against ' + thousands(nt.regime.down4) +
      ' down on the day · ' + thousands(nt.regime.up4_10d) + ' against ' + thousands(nt.regime.down4_10d) + ' over ' + br.ratio_long_sessions + ' sessions, ratio ' + nt.regime.ratio_10d.toFixed(2) + '.');
    const fx = await facts(p);
    check(`${tag}: the facts say what was removed, and count the stratum's bursts and the tickets the plan rules wrote`, fx.includes(opening('admitted', a)), [opening('admitted', a), fx]);
    eq(`${tag}: the tickets the study set aside unwalked are named as some of those written`, fx.includes('ticket' + (a.tickets === 1 ? '' : 's') + ' at full size, ' + thousands(bk.basis_mismatch) + ' of them set aside unwalked because the later records do not carry the signal’s own bar'), !!bk.basis_mismatch);
    // final: the hold is over AND no row of the stratum can still move
    const final = nt.complete && !a.movable;
    if (st.n > 0) {
      check(`${tag}: the facts print the wins and the sum at two places`, fx.includes(thousands(st.wins) + ' won, ' + thousands(st.losses) + ' lost, ' + thousands(st.breakeven) + ' even · ' + R2(st.sum_r) + ' in all'), fx);
      eq(`${tag}: a mean is printed as a rate only from the record's minimum of settled tickets`, [fx.includes(R3(st.mean_r) + ' per settled ticket, median ' + R2(st.median_r)), fx.includes('too few for a rate, which the record reads from ' + plural(min, 'settled ticket'))],
        [st.n >= min, st.n < min]);
      eq(`${tag}: the pill prints the mean from the minimum, the sum under it, and the settled count`, pl, pillOf(a, min));
      eq(`${tag}: "so far" while the hold runs or a row can still move`, fx.includes(thousands(st.n) + ' settled so far'), !final);
    } else {
      check(`${tag}: nothing settled is said so`, fx.includes('none settled') && !fx.includes(' won,'), fx);
      eq(`${tag}: "yet" while the hold runs or a row can still move`, fx.includes('none settled yet'), !final);
      eq(`${tag}: the pill counts the pending tickets`, pl, pillOf(a, min));
    }
    eq(`${tag}: a night whose hold is over with rows that can still move says so`, fx.includes('The hold is over, but ' + plural(a.movable, 'row') + ' can still move'), nt.complete && a.movable > 0);
    eq(`${tag}: pending and open are told apart, each from its own bucket`, [fx.includes(thousands(bk.pending) + ' pending'), fx.includes(thousands(bk.open) + ' still open')], [!!bk.pending, !!bk.open]);
    eq(`${tag}: the bursts without a ticket are counted by cause, and a set-aside ticket is not among them`, [fx.includes(thousands(bk.no_ticket) + ' the plan rules would not write a ticket for'), /Without a ticket:[^\n]*set aside/.test(fx)], [!!bk.no_ticket, false]);
    eq(`${tag}: an unfinished hold is said so, dated by the records read, and a finished one is not`, fx.includes('The ' + hold + '-session hold runs through ' + dayWords(nt.horizon) + '; the records read here end on ' + dayWords(asOf) + ', so nothing here is final.'), !nt.complete);
    const fr = nt.first_read && nt.first_read.admitted;
    eq(`${tag}: an earlier read is quoted only where the file carries one`, fx.includes('The first read, with records through'), !!(fr && (fr.n || st.n)));
    if (fr && (fr.n || st.n)) {
      eq(`${tag}: the first read says it came before the hold ended only where it did`, fx.includes('before every ticket had had its ' + hold + ' sessions'), !nt.first_read.horizon_passed);
      const same = fr.n === st.n && fr.sum_r === st.sum_r;
      check(`${tag}: the first read is quoted by the minimum's rule, then the re-read dated by its records`, fx.includes(': ' + outcome(fr, min) + (same ? '; unchanged on the records through ' + dayWords(asOf)
        : '; on the records through ' + dayWords(asOf) + ', ' + outcome(st, min))), [outcome(fr, min), outcome(st, min), fx]);
      eq(`${tag}: a night that moved after its hold says how many rows moved, and why`, fx.includes(plural(nt.first_read.moved.admitted, 'row') + ' having moved after the hold as later records carried bars the first read lacked'),
        !same && nt.first_read.horizon_passed && nt.first_read.moved.admitted > 0);
    }
    eq(`${tag}: the eyebrow says whether the hold is complete, as of the records read`, await tc(p, '#historical-evidence [data-find="eyebrow"]'), 'night ' + (k + 1) + ' of ' + N + ' · ' + nt.phase + ' · ' + (nt.complete ? hold + ' sessions complete' : 'inside its hold') + ' as of ' + shortDate(asOf));
    eq(`${tag}: the mean mark is hollow under the minimum and filled from it`, await p.locator('#historical-evidence .ss-find__night.is-current .ss-find__mean').evaluateAll((e) => e.map((c) => [c.dataset.readable, c.classList.contains('is-thin')])),
      st.mean_r === null ? [] : [[String(st.n >= min), st.n < min]]);
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
  check('the backtest bracket names the exact-lookback pass and counts its sessions', bracket === 'the backtest’s exact-lookback pass · ' + plural(F.backtest.lookback_260.evaluated.count, 'session') && (await p.locator('#historical-evidence path[data-bracket="backtest"]').count()) === 1, bracket);
  const ticks = await p.locator('#historical-evidence text[data-r-tick]').evaluateAll((e) => e.map((t) => ({ y: +t.getAttribute('y'), text: t.textContent, v: t.dataset.rTick })));
  check('the outcome axis is labelled in real multiples with zero among them', ticks.some((t) => t.text === '0R') && ticks.every((t) => /^[+−]?\d+R$/.test(t.text)), JSON.stringify(ticks));
  check('no two outcome ticks overlap', ticks.slice().sort((a, b) => a.y - b.y).every((t, i, s) => i === 0 || t.y - s[i - 1].y >= 11), JSON.stringify(ticks));
  eq('the first published night is said to follow sessions with no scan', await p.locator('#historical-evidence text[data-note="before"]').count(), F.market.sessions[0].date < F.nights[0].session ? 1 : 0);
  eq('the note stands on its own ground and clear of every night\'s marks', await noteClear(p), { ground: true, under: 0 });
  eq('every session has a hit column', await p.locator('#historical-evidence rect.ss-find__hit[data-hit][data-i]').count(), F.market.sessions.length);
  eq('the date axis is labelled', (await p.locator('#historical-evidence text.ss-find__date').count()) >= 3, true);
  const busiest = F.nights.reduce((b, n, k) => n.strata.admitted.r.length > F.nights[b].strata.admitted.r.length ? k : b, 0);
  for (const k of [...new Set([0, Math.floor(N / 2), busiest])]) {
    const nt = F.nights[k];
    await p.locator(`#historical-evidence [data-find-night="${nt.session}"]`).click(); await settle(p);
    const drawn = await p.locator('#historical-evidence .ss-find__night.is-current .ss-find__r').evaluateAll((e) => e.map((c) => Number(c.dataset.r)));
    const list = nt.strata.admitted.r;
    check(`night ${k + 1}: every drawn R is one the file lists, and all of them`, drawn.length === list.length && drawn.every((v) => list.includes(v)), JSON.stringify([drawn, list]));
    eq(`night ${k + 1}: the mean mark carries the file's mean`, await attr(p, '#historical-evidence .ss-find__night.is-current .ss-find__mean', 'data-mean'), nt.strata.admitted.settled.mean_r === null ? null : String(nt.strata.admitted.settled.mean_r));
  }
  eq('a night with nothing settled draws no mean, so nothing reads as a mean of zero', await p.locator('#historical-evidence .ss-find__mean').count(), F.nights.filter((n) => n.strata.admitted.settled.mean_r !== null).length);
  check('the file has a night with nothing settled, so the line above can fail', F.nights.some((n) => n.strata.admitted.settled.mean_r === null));
  eq('every mean of fewer than the minimum is hollow, every other filled', await p.locator('#historical-evidence .ss-find__mean.is-thin').count(), F.nights.filter((n) => n.strata.admitted.settled.mean_r !== null && n.strata.admitted.settled.n < min).length);
  check('the file has a mean on each side of the minimum, so the line above can fail', F.nights.some((n) => n.strata.admitted.settled.n >= min) && F.nights.some((n) => n.strata.admitted.settled.n && n.strata.admitted.settled.n < min));
  // the current night's dots are ringed, and keep the ticket's colour: the mean's colour means only the mean
  eq('the current night\'s dots are ringed and keep the colour the legend gives a ticket', await p.evaluate(() => {
    const st = (s) => { const c = document.querySelector('#historical-evidence ' + s); return c && getComputedStyle(c); };
    const cur = st('.ss-find__night.is-current .ss-find__r'), other = st('.ss-find__night:not(.is-current):not(.is-ghost) .ss-find__r') || st('.ss-find__night.is-ghost .ss-find__r');
    const mean = st('.ss-find__mean:not(.is-thin)'), key = st('[data-find="legend"] .ss-find__key--dot');
    return [cur.fill === other.fill, cur.stroke !== other.stroke, cur.fill !== mean.fill, cur.fill === key.backgroundColor];
  }), [true, true, true, true]);

  // ---- 3. the stratum control recounts the dots and retables
  const kMid = 5, mid = F.nights[kMid];
  await p.locator(`#historical-evidence [data-find-night="${mid.session}"]`).click(); await settle(p);
  const pressed = () => p.locator('#historical-evidence button[data-find-stratum][aria-pressed="true"]').evaluateAll((e) => e.map((b) => b.dataset.findStratum));
  eq('the control opens on the A-quality stratum', [await attr(p, ROOTSEL, 'data-stratum'), await pressed()], ['admitted', ['admitted']]);
  eq('the stratum tabs keep their casing', await p.locator('#historical-evidence button[data-find-stratum]').evaluateAll((e) => e.map((b) => b.innerText)), ['A-quality', 'graded B', 'graded C', 'graded skip', 'vetoed', 'every burst']);
  eq('the control is a captioned group', await p.evaluate(() => { const g = document.querySelector('#historical-evidence .sc-field--group'); const l = g && g.querySelector('.sc-field__label'); return l && l.textContent; }), 'tickets');
  const nightsTable = '#historical-evidence details[data-find="table-nights"]', marketTable = '#historical-evidence details[data-find="table-market"]';
  const rTable = '#historical-evidence details[data-find="table-r"]';
  // the twins are opened once and the nights table scrolled sideways; a stratum change keeps both as the reader left them
  await p.locator(nightsTable + ' > summary').click(); await p.locator(marketTable + ' > summary').click(); await settle(p);
  await p.locator(nightsTable + ' .sc-table-scroll').evaluate((s) => { s.scrollLeft = 160; }); await settle(p);
  const leftBefore = await p.locator(nightsTable + ' .sc-table-scroll').evaluate((s) => s.scrollLeft);
  check('the nights table scrolls sideways, so the kept scroll below can fail', leftBefore > 0, leftBefore);
  for (const [s, block] of [['all', (n) => n.all], ['B', (n) => n.strata.B], ['vetoed', (n) => n.strata.vetoed]]) {
    await p.locator(`#historical-evidence [data-find-stratum="${s}"]`).click(); await settle(p);
    eq(`stratum ${s}: the root and the pressed tab move`, [await attr(p, ROOTSEL, 'data-stratum'), await pressed()], [s, [s]]);
    eq(`stratum ${s}: the step is kept`, await stepOf(p), kMid + 1);
    eq(`stratum ${s}: every settled R of the stratum is a dot`, await dots(p), sum(F.nights.map((n) => block(n).r.length)));
    const b = block(mid), fx = await facts(p);
    check(`stratum ${s}: the facts say what this stratum removed, and count its bursts and the tickets the plan rules would have written`, fx.includes(opening(s, b)), [opening(s, b), fx]);
    eq(`stratum ${s}: the pill prints the stratum's outcome by the minimum's rule`, await pill(p), pillOf(b, min));
    eq(`stratum ${s}: both twins are still open, and the nights table still scrolled where it was`, [await p.locator(nightsTable).evaluate((d) => d.open), await p.locator(marketTable).evaluate((d) => d.open),
      await p.locator(nightsTable + ' .sc-table-scroll').evaluate((x) => x.scrollLeft)], [true, true, leftBefore]);
    eq(`stratum ${s}: the nights table carries every night`, (await rows(p, nightsTable)).length, N);
    const row = (await rows(p, nightsTable))[kMid];
    eq(`stratum ${s}: the current night's row is the file's, cell by cell`, row, [dayWords(mid.session), mid.regime.verdict, mid.regime.ratio_10d.toFixed(2), thousands(mid.bursts),
      thousands(mid.a_quality.mechanical), thousands(mid.a_quality.final), thousands(mid.tickets_published), thousands(b.rows), thousands(b.tickets), thousands(b.buckets.basis_mismatch),
      thousands(b.settled.n), thousands(b.settled.wins), thousands(b.settled.losses), thousands(b.settled.breakeven), b.settled.sum_r === null ? '—' : signed(b.settled.sum_r, 2),
      b.settled.n >= min ? signed(b.settled.mean_r, 3) : '—', thousands(b.buckets.uncertain), thousands(b.buckets.not_filled), thousands(b.buckets.open), thousands(b.buckets.pending)]);
    await p.locator(rTable + ' > summary').click(); await settle(p);
    eq(`stratum ${s}: the R table lists every settled R of the night, as the study wrote it`, (await rows(p, rTable))[kMid],
      [dayWords(mid.session), thousands(b.settled.n), b.r.length ? b.r.map((v) => signed(v, 2)).join(' ') : 'none']);
    await p.locator(rTable + ' > summary').click(); await settle(p);
  }
  // a night whose hold is over with nothing settled in a stratum: "none settled", never "yet"
  const over = F.nights.flatMap((n, k) => ['admitted', 'B', 'C', 'skip', 'vetoed'].filter((x) => n.complete && !n.strata[x].movable && n.strata[x].settled.n === 0).map((x) => ({ k, x })))[0];
  check('the file has a final night with nothing settled in some stratum, so the next line can fail', !!over);
  if (over) {
    await p.locator(`#historical-evidence [data-find-stratum="${over.x}"]`).click(); await settle(p);
    await p.locator(`#historical-evidence [data-find-night="${F.nights[over.k].session}"]`).click(); await settle(p);
    const ofx = await facts(p);
    check(`a finished night with nothing settled says so without "yet" (${F.nights[over.k].session}, ${over.x})`, ofx.includes('; none settled') && !ofx.includes('none settled yet'), ofx);
  }
  await p.locator(`#historical-evidence [data-find-night="${mid.session}"]`).click(); await settle(p);
  await p.locator('#historical-evidence [data-find-stratum="admitted"]').click(); await settle(p);
  eq('back to A-quality the dots are recounted', [await attr(p, ROOTSEL, 'data-stratum'), await dots(p)], ['admitted', sum(F.nights.map((n) => n.strata.admitted.r.length))]);
  eq('the three tables are named, focusable regions, as every twin in the app', await p.locator('#historical-evidence .ss-find__tables .sc-table-scroll').evaluateAll((e) => e.map((x) => [x.getAttribute('tabindex'), x.getAttribute('role'), x.getAttribute('aria-label')])),
    [['0', 'region', 'Nights as a table'], ['0', 'region', 'Every settled R as a table'], ['0', 'region', 'Market sessions as a table']]);

  // ---- 4. the market table: every session the records know
  if (!(await p.locator(marketTable).evaluate((d) => d.open))) { await p.locator(marketTable + ' > summary').click(); await settle(p); }
  check('the market table\'s caption says which sessions a gate read and which a later history carries', (await tc(p, marketTable + ' caption')).includes('on a published night the counts and the ratio its own gate read, on any other a later record’s history of the session'));
  const mrows = await rows(p, marketTable);
  eq('the market table carries every session', mrows.length, F.market.sessions.length);
  eq('the first row prints the first session\'s ratio', mrows[0][3], F.market.sessions[0].ratio_10d.toFixed(2));
  eq('publication rows and history rows say where they were read from', [mrows.filter((r) => r[5].includes('its own publication')).length, mrows.filter((r) => r[5].includes('the history of')).length],
    [F.market.sessions.filter((s) => s.basis === 'publication').length, F.market.sessions.filter((s) => s.basis === 'history').length]);
  eq('every session a later history reads differently says so, with its counts and its ratio', mrows.map((r) => r[5]).filter((c) => c.includes('(a later history')),
    F.market.sessions.filter((s) => s.later).map((s) => 'its own publication ' + s.source + ' (a later history, ' + s.later.source + ', reads ' + thousands(s.later.up4) + ' / ' + thousands(s.later.down4) + ', ratio ' + s.later.ratio_10d.toFixed(2) + ')'));
  check('the file has a night a later history reads differently only in its counts, so the line above can fail on a ratio-only rule', F.market.sessions.some((s) => s.later && s.later.ratio_10d === s.ratio_10d));
  const swap = F.market.sessions.findIndex((s) => s.up4 !== s.down4);
  eq('a market row prints the session\'s up and down in that order', [mrows[swap][1], mrows[swap][2]], [thousands(F.market.sessions[swap].up4), thousands(F.market.sessions[swap].down4)]);
  eq('a session with no publication says so', mrows.filter((r) => r[4] === 'no publication').length, F.market.sessions.filter((s) => !s.verdict).length);

  // ---- 6. a hit column: hover names the session, a mouse click takes the nearest published night
  const target = F.nights[3], ts = F.market.sessions.find((s) => s.date === target.session);
  await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p);
  await p.locator(`#historical-evidence rect[data-hit="${target.session}"]`).hover(); await settle(p, 150);
  const tip = p.locator('#historical-evidence .ss-find__chart .sc-tooltip.is-on');
  eq('hovering a column shows the tooltip', await tip.isVisible(), true);
  const tipText = await tip.innerText();
  const tb = target.strata.admitted;
  check('the tooltip prints the session\'s ratio, counts and verdict', tipText.includes(ts.ratio_10d.toFixed(2)) && tipText.includes(thousands(ts.up4) + ' / ' + thousands(ts.down4)) && tipText.includes('verdict ' + ts.verdict), tipText);
  check('the tooltip prints the tickets the plan rules wrote and the outcome by the minimum\'s rule', tipText.includes(thousands(tb.tickets)) && tipText.includes('tickets the plan rules wrote, A-quality')
    && (tb.settled.n >= min ? tipText.includes(R3(tb.settled.mean_r)) && tipText.includes('mean R, ' + thousands(tb.settled.n) + ' settled')
      : tipText.includes(R2(tb.settled.sum_r)) && tipText.includes('R in all, ' + thousands(tb.settled.n) + ' settled, too few for a rate')) && tipText.includes(plural(target.bursts, 'burst')), tipText);
  if (ts.later) check('the tooltip names a later history that reads the night differently', tipText.includes(thousands(ts.later.up4) + ' / ' + thousands(ts.later.down4) + ', ' + ts.later.ratio_10d.toFixed(2)) && tipText.includes('a later history, ' + ts.later.source), tipText);
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
  await p.locator(`#historical-evidence [data-find-night="${F.nights[N - 2].session}"]`).click(); await settle(p);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 900);
  eq('Play stops at the last night and says Play again', [await stepOf(p), await playWord(p), await p.evaluate(() => window.SCStock.findingsHandle.playing())], [N, 'Play', false]);
  await p.locator('#historical-evidence [data-find-night]').last().click(); await settle(p);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 120);
  eq('Play from the last night starts over', await stepOf(p), 1);
  // scrolling the replay off the screen stops it: the stepping is for a reader who is watching
  await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 120);
  await p.evaluate(() => window.scrollTo(0, 0)); await settle(p, 900);
  const scrolled = await stepOf(p); await settle(p, 700);
  eq('scrolled off the screen Play has stopped and the night holds', [await stepOf(p), await playWord(p)], [scrolled, 'Play']);
  await p.locator('#historical-evidence .ss-find__stage').scrollIntoViewIfNeeded(); await settle(p, 150);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 120);
  // leaving the view stops it too
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
  check('the rates line counts the uncertain and unfilled tickets, the bursts and the rules from the summary, in place',
    rates.includes(' · ' + thousands(prod.plans.uncertain) + ' uncertain on daily bars · ' + thousands(prod.plans.not_filled) + ' not filled · ')
    && rates.includes(' · ' + plural(L.candidates.bursts, 'burst') + ' scanned · rules ' + L.rules_version + ' · ') && rates.includes(plural(L.lookback.equivalence.compared, 'shared session')), rates);
  const brows = await rows(p, '#historical-evidence [data-find="backtest-table"]');
  eq('the backtest table has the two blocks, their splits and the exact lookback', brows.length, 2 + Object.keys(cf.by_regime).length + Object.keys(cf.by_grade).length + 2);
  // a gate row, the page's rule written again: rates only where the summary read them
  const gateRow = (label, g) => [label, thousands(g.tickets), thousands(g.settled.n), thousands(g.settled.wins) + ' / ' + thousands(g.settled.losses) + ' / ' + thousands(g.settled.breakeven),
    signed(g.settled.sum_r, 2), g.settled.readable ? signed(g.settled.avg_r, 2) : '—', g.settled.readable ? signed(g.settled.median_r, 2) : '—',
    g.settled.readable ? Math.round(g.settled.win_rate * 100) + '%' : '—', thousands(g.plans.uncertain), thousands(g.plans.not_filled), g.settled.readable ? signed(g.settled.spy_avg_pct, 2) + '%' : '—'];
  eq('the production row is the summary\'s, cell by cell', brows[0], gateRow('production', prod));
  eq('the counterfactual row is named the gate removed and is the summary\'s, cell by cell', brows[1], gateRow('gate removed', cf));
  eq('the exact-lookback rows are the second summary\'s, cell by cell', brows.slice(-2), [gateRow(plural(X.evaluated.count, 'session') + ': production', X.gates.production),
    gateRow(plural(X.evaluated.count, 'session') + ': gate removed', X.gates.no_regime_gate)]);
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
  eq('each run-6 row is the summary\'s and the publication\'s, cell by cell', r6, days.map((d) => {
    const s = F.run6.sessions[d], c = s.policies.C, o = s.original;
    return [dayWords(d), o.ratio_10d.toFixed(2) + ' (' + thousands(o.up4_10d) + ' / ' + thousands(o.down4_10d) + ')', c.ratio_10d.toFixed(2), thousands(c.up4_10d) + ' / ' + thousands(c.down4_10d),
      c.ratio_10d_bounds.map((v) => v.toFixed(2)).join(' to ') + ' over ' + plural(c.unknown_contributors, 'unknown'), thousands(o.universe) + ' published, ' + thousands(c.counted_universe) + ' fresh',
      o.verdict + ' published, ' + c.independent_verdict + ' fresh', c.rules_fired.map((r) => r.replace(/_/g, ' ')).join(', ')];
  }));
  const r6facts = await txt(p, '#historical-evidence p[data-find="run6-facts"]');
  check('the run-6 facts name every blocking stock, the download and each session\'s own partial count', F.run6.blocking_names.every((n) => r6facts.includes(n)) && r6facts.includes(thousands(F.run6.download.queries_completed) + ' of ' + thousands(F.run6.download.queries_total) + ' queries')
    && days.every((d) => r6facts.includes(thousands(F.run6.sessions[d].partial) + ' on ' + shortDate(d))), r6facts);
  eq('the run-6 table is named by its run number', await attr(p, '#historical-evidence [data-find="run6-table"]', 'aria-label'), 'Run ' + thousands(F.run6.public.run_number) + ' as a table');
  const readAs = await p.locator('#historical-evidence ul[data-find="read-as"] > li').evaluateAll((e) => e.map((li) => li.textContent));
  eq('the reading is five sentences', readAs.length, 5);
  eq('the nights inside their hold are the file\'s count of them', ns.inside_hold, F.nights.filter((n) => !n.complete).length);
  readingHolds(F, readAs, eq, check, '');
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
    check(`${tag}: the stage, the caption and the index stack, the words a step changes under the stage`, await q.evaluate(() => {
      const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect();
      return r('.ss-find__caption').top >= r('.ss-find__stage').bottom - 1 && r('.ss-find__side').top >= r('.ss-find__caption').bottom - 1;
    }));
    eq(`${tag}: the note before the first night is on its own ground and over no mark, or left out`, await noteClear(q), { ground: true, under: 0 });
    // a narrow chart has no room for the tooltip beside a column: none is shown, and nothing scrolls sideways
    for (const col of [Math.floor(F.market.sessions.length / 2), F.market.sessions.length - 1, 0]) {
      await q.locator(`#historical-evidence rect[data-hit="${F.market.sessions[col].date}"]`).hover({ force: true }); await settle(q, 120);
    }
    eq(`${tag}: hovering columns shows no tooltip on a narrow chart and scrolls nothing sideways`, [await q.locator('#historical-evidence .ss-find__chart .sc-tooltip.is-on').count(), await sideways(q)], [0, false]);
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
    eq(`${tag}: the chooser's hint is true below the chart as beside it`, await txt(q, '#historical-evidence [data-find="pick"] .sc-pick__hint'), 'Nearest first. The list of nights reaches each one exactly.');
    eq(`${tag}: the chooser's first night has the focus`, await q.evaluate(() => document.activeElement && document.activeElement.dataset.pickNight), night.session);
    eq(`${tag}: the chooser's Close stays on one line`, await q.locator('#historical-evidence [data-find="pick"] [data-pick="close"]').evaluate((b) => b.getClientRects().length === 1 && b.getBoundingClientRect().height < 2.4 * parseFloat(getComputedStyle(b).fontSize)), true);
    const second = offered[1];
    await q.locator(`#historical-evidence [data-find="pick"] [data-pick-night="${second}"]`).click(); await settle(q);
    eq(`${tag}: choosing a night takes that night and closes the chooser`, [await nightOf(q), await q.locator('#historical-evidence [data-find="pick"]').count()], [second, 0]);
    // a tap during Play opens the chooser and stops Play, so the night cannot change under the finger
    await q.locator('#historical-evidence [data-find="play"]').tap(); await settle(q, 60);
    await q.locator('#historical-evidence .ss-find__svg').evaluate((e) => e.scrollIntoView({ block: 'center' })); await settle(q, 60);
    const spot2 = await q.evaluate((s) => { const c = document.querySelector('#historical-evidence .ss-find__night[data-night="' + s + '"] .ss-find__mean'); const b = c.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; }, night.session);
    await q.touchscreen.tap(spot2.x, spot2.y); await settle(q, 40);
    const opened = [await q.locator('#historical-evidence [data-find="pick"]').count(), await stepOf(q)];
    await settle(q, 700);
    eq(`${tag}: a tap during Play stops it; the chooser stays open and the night holds past an interval`, [await playWord(q), await q.locator('#historical-evidence [data-find="pick"]').count(), await stepOf(q)], ['Play', 1, opened[1]]);
    eq(`${tag}: the tap opened the chooser`, opened[0], 1);
    await q.keyboard.press('Escape'); await settle(q);
    const heldNight = await nightOf(q);
    await q.touchscreen.tap(spot2.x, spot2.y); await settle(q, 200);
    await q.keyboard.press('Escape'); await settle(q);
    eq(`${tag}: Escape closes it, the night unchanged, the focus back on the stage`, [await q.locator('#historical-evidence [data-find="pick"]').count(), await nightOf(q), await q.evaluate(() => document.activeElement && document.activeElement.classList.contains('ss-find__stage'))], [0, heldNight, true]);
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
  altered.rules.record.open_plan_sessions = 7;
  // every rule number and count a caption quotes, moved, so a number typed into a caption prints the old one
  Object.assign(altered.rules.breadth, { ratio_long_sessions: 12, burst_pct: 5 });
  altered.rules.breadth.size_multiplier.yellow = 0.25;
  altered.rules.pipeline.yellow_grades = ['A+', 'A'];
  altered.rules.record.scorecard_min_plans = 7;
  altered.market.thresholds = { ratio_10d_red: 1.1, ratio_10d_yellow: 2.2 };
  Object.assign(altered.nights_summary, { nights: 99, bursts: 12345, tickets_published: 3 });
  altered.backtest.lookback_130.evaluated.count = 777;
  const a = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(altered)) });
  eq('altered file: the replay is ready', await ready(a.page), 'ready');
  const afx = await facts(a.page);
  check('a changed sum in the file is printed as given, so the page computes nothing', afx.includes('+123.45R in all') && !afx.includes(R2(F.nights[0].strata.admitted.settled.sum_r) + ' in all'), afx);
  check('and the mean beside it is still the file\'s own, not re-derived from the sum', (await pill(a.page)).includes(R3(F.nights[0].strata.admitted.settled.mean_r)), await pill(a.page));
  check('a changed count of A-quality after the reader is printed as given, not summed from grades', (await txt(a.page, '#historical-evidence [data-find="text"]')).includes('after it, ' + thousands(4321) + ' stood at A-quality'));
  check('a changed hold is printed as given, so no caption types its length', (await tc(a.page, '#historical-evidence [data-find="eyebrow"]')).endsWith(' · 7 sessions complete as of ' + shortDate(asOf)), await tc(a.page, '#historical-evidence [data-find="eyebrow"]'));
  const aLead = await txt(a.page, HOST + ' p[data-find="lead"]'), aKey = await txt(a.page, '#historical-evidence [data-find="regime-key"]');
  check('the lead prints the changed night, burst and ticket counts', aLead.includes('Over the 99 published nights') && aLead.includes('published 3 tickets out of 12,345 bursts scanned'), aLead);
  check('the key prints the changed thresholds, size and grades', aKey.includes('Dashed lines, the 12-session ratio rule: under 1.1 it says red') && aKey.includes('under 2.2 yellow, size × 0.25, A+ and A only'), aKey);
  check('the legend, the panel and the description print the changed ratio length and burst size', (await txt(a.page, '#historical-evidence [data-find="legend"]')).includes('12-session ratio')
    && (await tc(a.page, '#historical-evidence text.ss-find__panel')) === '12-session ratio, up 5% against down' && (await tc(a.page, '#historical-evidence .ss-find__svg desc')).includes('the 12-session ratio of stocks up 5% to stocks down'));
  eq('the thresholds are labelled at the axis as changed', [await tc(a.page, '#historical-evidence text[data-ref-label="red"]'), await tc(a.page, '#historical-evidence text[data-ref-label="yellow"]')], ['1.1', '2.2']);
  check('the market line prints the changed burst size and ratio length', (await facts(a.page)).includes(' up 5% against ') && (await facts(a.page)).includes(' over 12 sessions, ratio '), await facts(a.page));
  check('the strip prints the changed session count', (await txt(a.page, '#historical-evidence dl[data-find="backtest-strip"]')).includes('777'));
  // the changed minimum: a night between it and the record's own reads as a rate now
  const between = F.nights.findIndex((n) => n.strata.admitted.settled.n >= 7 && n.strata.admitted.settled.n < min);
  check('the file has a night between the changed minimum and its own, so the next line can fail', between >= 0);
  await a.page.locator(`#historical-evidence [data-find-night="${F.nights[between].session}"]`).click(); await settle(a.page);
  check('a changed minimum moves which nights read as a rate', (await pill(a.page)) === R3(F.nights[between].strata.admitted.settled.mean_r) + ' · ' + thousands(F.nights[between].strata.admitted.settled.n) + ' settled', await pill(a.page));
  const inside = F.nights.find((n) => !n.complete);
  await a.page.locator(`#historical-evidence [data-find-night="${inside.session}"]`).click(); await settle(a.page);
  check('and a night inside its hold names the changed length too', (await facts(a.page)).includes('The 7-session hold runs through ' + dayWords(inside.horizon)), await facts(a.page));
  eq('altered file errors', a.errors, []);
  await a.context.close();
  // branches no committed night reaches: a yellow and a green night, a positive stratum, a readable
  // confirmatory split, an unreadable backtest that saw green nights. One file, internally consistent
  // where the page reads it, so each sentence's other side is driven
  const branches = structuredClone(F);
  const ny = branches.nights[3], ngr = branches.nights[4];
  Object.assign(ny.regime, { verdict: 'yellow', size_multiplier: branches.rules.breadth.size_multiplier.yellow, reasons: ['ten-session ratio under the yellow line'] });
  Object.assign(ngr.regime, { verdict: 'green', size_multiplier: branches.rules.breadth.size_multiplier.green, reasons: [] });
  branches.nights_summary.verdicts = { red: N - 2, yellow: 1, green: 1 };
  branches.reading.phases.exploratory.red_nights -= 2;
  branches.reading.phases.exploratory.strata.B.mean_r = 0.12;
  Object.assign(branches.study.summary.phases.confirmatory, { settled: { n: 27, wins: 15, losses: 12, breakeven: 0, sum_r: 3.81, mean_r: 0.141, median_r: 0.2 },
    scorecard: Object.assign({}, branches.study.summary.phases.confirmatory.scorecard, { readable: true }) });
  branches.backtest.lookback_130.regimes.verdicts.green = 5;
  branches.backtest.lookback_130.gates.production.settled.readable = false;
  const bb = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(branches)) });
  eq('branches file: the replay is ready', await ready(bb.page), 'ready');
  eq('branches: the legend keys the yellow and green nights too', await bb.page.locator('#historical-evidence [data-find="legend"] [data-find-key]').evaluateAll((e) => e.map((x) => x.dataset.findKey)),
    ['red', 'yellow', 'green', 'thin'].concat(frozen ? ['freeze'] : []));
  for (const [nt, chip] of [[ny, 'yellow size × ' + branches.rules.breadth.size_multiplier.yellow], [ngr, 'green full size']]) {
    await bb.page.locator(`#historical-evidence [data-find-night="${nt.session}"]`).click(); await settle(bb.page);
    check(`branches: a ${nt.regime.verdict} night's market line names its size`, (await bb.page.locator('#historical-evidence [data-find="facts"] > li').first().textContent()).startsWith(chip + ' · '), await facts(bb.page));
  }
  const bRead = await bb.page.locator('#historical-evidence ul[data-find="read-as"] > li').evaluateAll((e) => e.map((li) => li.textContent));
  readingHolds(branches, bRead, eq, check, 'branches: ');
  check('branches: a positive stratum withdraws the refusals\' value', bRead[0].includes('Not every stratum is under zero') && !bRead[0].includes('had value in sum'), bRead[0]);
  check('branches: a readable confirmatory split is printed as the study\'s result', bRead[1].includes('the study’s confirmatory result is +0.141R per settled ticket over 27.'), bRead[1]);
  check('branches: the two nights that were not red are left out and named', bRead[4].startsWith('2 published nights here were not red and are left out'), bRead[4]);
  const bStrip = await txt(bb.page, '#historical-evidence dl[data-find="backtest-strip"]'), bRates = await txt(bb.page, '#historical-evidence p[data-find="backtest-rates"]');
  check('branches: a backtest with green nights says so in the strip and the text', bStrip.includes('on yellow and green nights') && !(await txt(bb.page, '#historical-evidence section[data-find-block="backtest"]')).includes('never green'), bStrip);
  check('branches: an unreadable backtest prints its count and no rate', bRates.startsWith(plural(F.backtest.lookback_130.gates.production.settled.n, 'settled ticket') + ', too few for a rate (the summary reads one from ' + F.backtest.lookback_130.gates.production.settled.min_read + ')') && !bRates.includes('Win rate'), bRates);
  eq('branches file errors', bb.errors, []);
  await bb.context.close();
  // a long list of nights: the caption stays under the stage on a desktop, and before the list on a phone
  const many = structuredClone(F);
  many.nights = F.market.sessions.map((s, i) => Object.assign(structuredClone(F.nights[i % N]), { session: s.date }));
  for (const width of [1280, 390]) {
    const mm = await load(FULL, width, { height: width === 1280 ? 900 : 844, beforeLoad: routed(JSON.stringify(many)) });
    eq(`many nights ${width}: the replay is ready`, await ready(mm.page), 'ready');
    await mm.page.locator('#historical-evidence [data-find="next"]').click(); await settle(mm.page);
    const gap = await mm.page.evaluate(() => { const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect(); return [r('.ss-find__caption').top - r('.ss-find__stage').bottom, r('.ss-find__side').top - r('.ss-find__caption').bottom]; });
    check(`many nights ${width}: the caption follows the stage within a gap, however long the list`, gap[0] >= 0 && gap[0] <= 48, gap);
    if (width === 390) check('many nights 390: the list of nights follows the caption', gap[1] >= 0, gap);
    eq(`many nights ${width} errors`, mm.errors, []);
    await mm.context.close();
  }
  // between the phone and the one-row width the tabs wrap: their caption stands over them, never between rows
  const tablet = await load(FULL, 768);
  eq('768: the replay is ready', await ready(tablet.page), 'ready');
  check('768: the tabs\' caption sits over them, not beside two rows of them', await tablet.page.evaluate(() => {
    const g = document.querySelector('#historical-evidence .ss-find__filter'), l = g.querySelector('.sc-field__label').getBoundingClientRect(), t = g.querySelector('.sc-tabs').getBoundingClientRect();
    return l.bottom <= t.top + 1;
  }));
  eq('768 errors', tablet.errors, []);
  await tablet.context.close();
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
    ['a night without its B stratum', JSON.stringify((() => { const x = structuredClone(F); delete x.nights[2].strata.B; return x; })()), 200, 'A night of the findings has a malformed stratum.'],
    ['an R that is not a number', JSON.stringify((() => { const x = structuredClone(F); x.nights[1].strata.admitted.r[0] = 'x'; return x; })()), 200, 'A night of the findings has a malformed stratum.'],
    ['a night without its phase', JSON.stringify((() => { const x = structuredClone(F); delete x.nights[0].phase; return x; })()), 200, 'A night of the findings is malformed.'],
    ['a market without its red threshold', JSON.stringify((() => { const x = structuredClone(F); delete x.market.thresholds.ratio_10d_red; return x; })()), 200, 'The findings carry no market.'],
    ['a run-6 session without its original', JSON.stringify((() => { const x = structuredClone(F); delete x.run6.sessions[Object.keys(x.run6.sessions)[0]].original; return x; })()), 200, 'The findings carry no fresh-bar reading.'],
    ['a backtest without its gates', JSON.stringify((() => { const x = structuredClone(F); delete x.backtest.lookback_130.gates; return x; })()), 200, 'The findings carry no backtest.'],
    ['a run-6 session that is null', JSON.stringify((() => { const x = structuredClone(F); x.run6.sessions[Object.keys(x.run6.sessions)[0]] = null; return x; })()), 200, 'The findings carry no fresh-bar reading.'],
    ['a gate reason that is not a sentence', JSON.stringify((() => { const x = structuredClone(F); x.nights[0].regime.reasons = [null]; return x; })()), 200, 'A night of the findings is malformed.'],
    ['a file without its reading', JSON.stringify((() => { const x = structuredClone(F); delete x.reading; return x; })()), 200, 'The findings carry no reading.'],
    ['a market session without its source', JSON.stringify((() => { const x = structuredClone(F); delete x.market.sessions[0].source; return x; })()), 200, 'The findings carry no market.'],
    ['a body that is not JSON', '{"version": ', 200, 'The validation findings did not load. Reload the page to try again.'],
    ['a backtest gate without its settled block', JSON.stringify((() => { const x = structuredClone(F); delete x.backtest.lookback_130.gates.production.settled; return x; })()), 200, 'The findings carry no backtest.'],
    // past the shape check, broken one block down: the replay that was drawn is taken away, never left half-built
    ['a counterfactual gate without its regime split', JSON.stringify((() => { const x = structuredClone(F); delete x.backtest.lookback_130.gates.no_regime_gate.by_regime; return x; })()), 200, 'The validation findings could not be read.'],
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

  // a stalled request ends in a sentence rather than a spinner: the wait is injected short, as Play's interval is
  const short = async (page) => { await page.addInitScript(() => { window.SCStock = Object.assign(window.SCStock || {}, { evidenceTimeout: 400, findingsInterval: 250 }); }); };
  for (const [name, glob, hostSel, state, sentence] of [
    ['the findings', '**/historical-findings.json*', HOST, 'findings', 'The validation findings did not load. Reload the page to try again.'],
    ['the study', '**/historical-validation.json*', '#historical-evidence [data-study]', 'study', 'The validation summary did not load. Reload the page to try again.'],
  ]) {
    const hang = await load(FULL, 1280, { beforeLoad: async (page) => { await short(page); await page.route(glob, () => {}); } });
    await hang.page.waitForFunction(([s, k]) => { const h = document.querySelector(s); return h && h.dataset[k] === 'error'; }, [hostSel, state], { timeout: 8000 }).catch(() => {});
    eq(`a stalled request for ${name} ends in the error state with one sentence`, [await attr(hang.page, hostSel, 'data-' + state), await txt(hang.page, hostSel + ' p[role="alert"]').catch(() => null)], ['error', sentence]);
    eq(`a stalled request for ${name} leaves no loading line and nothing marked busy`, [await hang.page.locator(hostSel + ' [data-evidence-loading]').count(), await attr(hang.page, hostSel, 'aria-busy')], [0, null]);
    await hang.context.close();
  }
  // the study file's own failures, each one sentence, the replay unaffected
  for (const [name, body, status, sentence] of [
    ['a 404', 'nope', 404, 'The validation summary did not load. Reload the page to try again.'],
    ['a wrong version', JSON.stringify({ version: 'historical-validation-v0' }), 200, 'Unknown study version.'],
  ]) {
    const sb = await load(FULL, 1280, { beforeLoad: async (page) => { await fast(page); await page.route('**/historical-validation.json*', (route) => route.fulfill({ status, contentType: 'application/json', body })); } });
    await sb.page.waitForFunction(() => { const h = document.querySelector('#historical-evidence [data-study]'); return h && h.dataset.study !== 'loading' && h.dataset.study !== 'waiting'; }, null, { timeout: 8000 });
    eq(`the study file, ${name}: ends in its error state with one sentence`, [await attr(sb.page, '#historical-evidence [data-study]', 'data-study'), await txt(sb.page, '#historical-evidence [data-study] p[role="alert"]')], ['error', sentence]);
    eq(`the study file, ${name}: the replay still renders`, await ready(sb.page), 'ready');
    eq(`the study file, ${name}: the only errors are the one this check served`, sb.errors.filter((x) => !/404/.test(x)), []);
    await sb.context.close();
  }
  // while a file is in flight its host says so in one line and is marked busy
  const slow = await load(FULL, 1280, { beforeLoad: async (page) => { await fast(page); await page.route('**/historical-findings.json*', async (route) => { await new Promise((r) => setTimeout(r, 1500)); await route.continue(); }); } });
  await slow.page.waitForSelector(HOST + ' [data-evidence-loading]', { timeout: 5000 });
  eq('in flight: the replay\'s host says it is loading and is marked busy', [await txt(slow.page, HOST + ' [data-evidence-loading]'), await attr(slow.page, HOST, 'aria-busy')], ['Loading the replay of the published nights…', 'true']);
  eq('in flight, then loaded: the line is gone and nothing is busy', [await ready(slow.page), await slow.page.locator(HOST + ' [data-evidence-loading]').count(), await attr(slow.page, HOST, 'aria-busy')], ['ready', 0, null]);
  eq('in flight page errors', slow.errors, []);
  await slow.context.close();

  // ---- 13. the live record wears no demo note, read at its own publication's instant so no later record can date the check
  const record = JSON.parse(await readFile(path.join(ROOT, 'docs', 'data.json'), 'utf8'));
  const liveNow = new Date(Date.parse(record.run.published_at) + 5 * 60 * 1000).toISOString();
  const live = await load('/docs/data.json', 1280, { now: liveNow });
  eq('the live record is not a fixture', await live.page.getAttribute('html', 'data-ss-demo'), 'false');
  eq('live: the replay is ready', await ready(live.page), 'ready');
  eq('live: no demo note', await live.page.locator(HOST + ' p[data-findings-demo]').count(), 0);
  eq('live: every night is listed', await live.page.locator('#historical-evidence [data-find-night]').count(), N);
  eq('live findings errors', live.errors, []);
  await live.context.close();
}
