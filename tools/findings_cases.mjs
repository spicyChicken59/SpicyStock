/* The Record view's historical findings (docs/app-findings.js over
   docs/historical-findings.json), read back through a real browser: the
   replay mounts on every Record visit, steps by button, index, hit column,
   keyboard and Play; every number a caption, a pill, a table or a block
   prints is a field of the committed file, held to that file read with fs
   and never to the page's prose; a stratum change recounts the dots and
   retables; the phone stacks it with nothing sideways; a routed copy of the
   file with one number changed prints that number (the page computes
   nothing), a 500 and a wrong version each leave the rest of the view
   standing; and the live record, which wears no demo note, renders it too.
   Judged against the JSON on disk, never against SCStock.findings. */
import { readFile } from 'node:fs/promises';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NOW = '2026-09-10T22:31:00Z';         // the fixtures' own instant
const LIVE_NOW = '2026-10-06T14:00:00Z';    // a Tuesday morning over the real 5 October record
const HOST = '#historical-evidence [data-findings]';
const settle = (p, ms) => p.waitForTimeout(ms || 80);
const txt = (p, sel) => p.locator(sel).first().innerText();
const tc = (p, sel) => p.locator(sel).first().textContent();
const attr = (p, sel, a) => p.locator(sel).first().getAttribute(a);
// the words the page uses for numbers, rebuilt here so a check never reads them off the page
const thousands = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const rr = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2) + 'R';
const signed = (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
const plural = (n, noun) => thousands(n) + ' ' + noun + (n === 1 ? '' : 's');
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const stepOf = (p) => p.evaluate(() => Number(document.querySelector('#historical-evidence [data-find-root]').getAttribute('data-step')));
const nightOf = (p) => attr(p, '#historical-evidence [data-find-root]', 'data-night');
const ghosts = (p) => p.locator('#historical-evidence .ss-find__night.is-ghost').count();
const dots = (p) => p.locator('#historical-evidence .ss-find__r').count();
const pill = (p) => tc(p, '#historical-evidence g[data-pill] text');
const facts = (p) => txt(p, '#historical-evidence [data-find="facts"]');
const sideways = (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
const rows = (p, sel) => p.locator(sel + ' tbody tr').evaluateAll((trs) => trs.map((tr) => Array.from(tr.querySelectorAll('td')).map((td) => td.textContent)));
const svgFits = (p) => p.evaluate(() => {
  const s = document.querySelector('#historical-evidence .ss-find__svg'), c = document.querySelector('#historical-evidence .ss-find__chart');
  return !!s && Math.abs(+s.getAttribute('width') - c.clientWidth) <= 2 && Math.abs(s.getBoundingClientRect().height - +s.getAttribute('height')) <= 2;
});
// loading -> ready | error; then, when ready, the svg the ResizeObserver may draw a frame later
async function ready(p) {
  await p.waitForFunction((sel) => { const h = document.querySelector(sel); return h && h.dataset.findings !== 'loading'; }, HOST, { timeout: 15000 });
  const state = await attr(p, HOST, 'data-findings');
  if (state === 'ready') await p.waitForSelector('#historical-evidence .ss-find__svg', { timeout: 5000 });
  await settle(p, 120);
  return state;
}

export async function checkFindings({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- findings: the record night by night');
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const F = JSON.parse(await readFile(path.join(ROOT, 'docs', 'historical-findings.json'), 'utf8'));
  const N = F.nights.length;
  const fast = (page) => page.addInitScript(() => { window.SCStock = Object.assign(window.SCStock || {}, { findingsInterval: 250 }); });
  const load = (dataUrl, width, extras) => open(browser, base, dataUrl, extras && extras.now || NOW, width,
    Object.assign({ lens: 'all', hash: '#/record', reducedMotion: 'reduce', beforeLoad: fast }, extras || {}));
  const FULL = '/tests/fixtures/page/full.json';

  // ---- 1. the mount over the fixture page
  const f = await load(FULL, 1280);
  const p = f.page;
  eq('the replay is ready on the Record view', await ready(p), 'ready');
  eq('a fixture page says the replay reads the public findings', await p.locator(HOST + ' p[data-findings-demo]').count(), 1);
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
  check('on a desktop the index sits beside the stage and the caption under the stage', await p.evaluate(() => {
    const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect();
    return r('.ss-find__side').left >= r('.ss-find__stage').right - 1 && r('.ss-find__caption').top >= r('.ss-find__stage').bottom - 1;
  }));
  const cursorAt = () => p.evaluate(() => document.querySelector('#historical-evidence g[data-cursor]').style.transform);
  const cursor1 = await cursorAt();

  // ---- 2. the step loop: every night's words are the file's
  for (let k = 0; k < N; k++) {
    const nt = F.nights[k], a = nt.strata.admitted, st = a.settled;
    if (k > 0) { await p.locator('#historical-evidence [data-find="next"]').click(); await settle(p); }
    const tag = `night ${k + 1}`;
    eq(`${tag}: the root names the session and the step`, [await nightOf(p), await attr(p, '#historical-evidence [data-find-root]', 'data-step')], [nt.session, String(k + 1)]);
    eq(`${tag}: is current in the index`, await attr(p, '#historical-evidence [data-find-night][aria-current="step"]', 'data-find-night'), nt.session);
    eq(`${tag}: its marks are current and the later nights are ghosts`, [await p.locator('#historical-evidence .ss-find__night.is-current').evaluateAll((e) => e.map((g) => g.dataset.night)), await ghosts(p)], [[nt.session], N - 1 - k]);
    eq(`${tag}: the count says where the reader is`, await txt(p, '#historical-evidence [data-find="count"]'), `Night ${k + 1} of ${N}`);
    const title = await txt(p, '#historical-evidence [data-find="title"]');
    check(`${tag}: the title carries the verdict and the ratio`, title.includes(nt.regime.verdict) && title.includes('ratio ' + nt.regime.ratio_10d.toFixed(2)), title);
    const text = await txt(p, '#historical-evidence [data-find="text"]');
    check(`${tag}: the text counts the bursts and the tickets published`, text.includes('found ' + plural(nt.bursts, 'burst')) && text.includes('published ' + plural(nt.tickets_published, 'ticket')), text);
    const fx = await facts(p);
    check(`${tag}: the facts count the A-quality tickets`, fx.includes(': ' + plural(a.rows, 'ticket')), fx);
    const pl = await pill(p);
    if (st.n > 0) {
      check(`${tag}: the facts print the wins and the summed R`, fx.includes(thousands(st.wins) + ' won') && fx.includes(rr(st.sum_r) + ' in all'), fx);
      check(`${tag}: the pill prints the mean and the settled count`, pl.includes(rr(st.mean_r)) && pl.includes(thousands(st.n) + ' settled'), pl);
    } else {
      check(`${tag}: nothing settled is said so`, fx.includes('none settled yet') && !fx.includes(' won'), fx);
      eq(`${tag}: the pill counts the pending tickets`, pl, a.buckets.pending ? plural(a.buckets.pending, 'ticket') + ' pending' : 'nothing settled');
    }
    eq(`${tag}: an unfinished hold is said so, a finished one is not`, fx.includes('runs through'), !nt.complete);
    const fr = nt.first_read && nt.first_read.admitted;
    eq(`${tag}: an earlier read is quoted only where the file carries one`, fx.includes('Read on'), !!(fr && fr.n));
    if (k === 1) {
      check('the cursor moved between night 1 and night 2', (await cursorAt()) !== cursor1 && /translateX\(/.test(await cursorAt()), [cursor1, await cursorAt()]);
      check('under reduced motion a step is not animated', await p.evaluate(() => !document.querySelector('#historical-evidence [data-find-root]').classList.contains('is-animated') && !/transform/.test(getComputedStyle(document.querySelector('#historical-evidence g[data-cursor]')).transitionProperty)));
    }
  }
  eq('Next is refused on the last night', await attr(p, '#historical-evidence [data-find="next"]', 'aria-disabled'), 'true');
  eq('Back is offered on the last night', await attr(p, '#historical-evidence [data-find="back"]', 'aria-disabled'), 'false');

  // ---- 5. the chart's own words, and the dots of a sampled night
  const refs = { red: await tc(p, '#historical-evidence text[data-ref-label="red"]'), green: await tc(p, '#historical-evidence text[data-ref-label="green"]'), yellow: await tc(p, '#historical-evidence text[data-ref-label="yellow"]') };
  check('the red line is named at the file\'s threshold', refs.red.includes(F.market.thresholds.ratio_10d_red.toFixed(1)) && refs.red.includes('no new longs'), refs.red);
  check('the green line is named at the file\'s threshold', refs.green.includes(F.market.thresholds.ratio_10d_yellow.toFixed(1)) && refs.green.includes('full size'), refs.green);
  check('the yellow band names its size and grades on a desktop', refs.yellow.includes('size × ' + F.rules.breadth.size_multiplier.yellow) && refs.yellow.includes(F.rules.pipeline.yellow_grades.join(' and ') + ' only'), refs.yellow);
  eq('the reference lines are drawn once each', await p.locator('#historical-evidence line[data-ref]').evaluateAll((e) => e.map((l) => l.dataset.ref).sort()), ['green', 'red']);
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
  eq('the control opens on the A-quality stratum', [await attr(p, '#historical-evidence [data-find-root]', 'data-stratum'), await pressed()], ['admitted', ['admitted']]);
  eq('the control is a captioned group', await p.evaluate(() => { const g = document.querySelector('#historical-evidence .sc-field--group'); const l = g && g.querySelector('.sc-field__label'); return l && l.textContent; }), 'tickets');
  const nightsTable = '#historical-evidence details[data-find="table-nights"]';
  for (const [s, block, phrase] of [['all', (n) => n.all, 'Had every burst been ticketed'], ['B', (n) => n.strata.B, 'Had every graded B burst been ticketed']]) {
    await p.locator(`#historical-evidence [data-find-stratum="${s}"]`).click(); await settle(p);
    eq(`stratum ${s}: the root and the pressed tab move`, [await attr(p, '#historical-evidence [data-find-root]', 'data-stratum'), await pressed()], [s, [s]]);
    eq(`stratum ${s}: the step is kept`, await stepOf(p), kMid + 1);
    eq(`stratum ${s}: every settled R of the stratum is a dot`, await dots(p), sum(F.nights.map((n) => block(n).r.length)));
    const fx = await facts(p);
    check(`stratum ${s}: the facts name the stratum and count its tickets`, fx.includes(phrase + ' at full size') && fx.includes(': ' + plural(block(mid).rows, 'ticket')), fx);
    const b = block(mid).settled;
    check(`stratum ${s}: the pill prints the stratum's mean`, (await pill(p)).includes(rr(b.mean_r)) && (await pill(p)).includes(thousands(b.n) + ' settled'), await pill(p));
    await p.locator(nightsTable + ' > summary').click(); await settle(p);
    eq(`stratum ${s}: the nights table opens with every night`, [await p.locator(nightsTable).evaluate((d) => d.open), (await rows(p, nightsTable)).length], [true, N]);
    const row = (await rows(p, nightsTable))[kMid];
    eq(`stratum ${s}: the current night's row counts the stratum's tickets and settled`, [row[6], row[7], row[11]], [thousands(block(mid).rows), thousands(b.n), signed(b.sum_r, 2)]);
  }
  await p.locator('#historical-evidence [data-find-stratum="admitted"]').click(); await settle(p);
  eq('back to A-quality the dots are recounted', [await attr(p, '#historical-evidence [data-find-root]', 'data-stratum'), await dots(p)], ['admitted', sum(F.nights.map((n) => n.strata.admitted.r.length))]);

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

  // ---- 6. a hit column: hover names the session, a click on a published night takes it
  const target = F.nights[3], ts = F.market.sessions.find((s) => s.date === target.session);
  await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p);
  await p.locator(`#historical-evidence rect[data-hit="${target.session}"]`).hover(); await settle(p, 150);
  const tip = p.locator('#historical-evidence .ss-find__chart .sc-tooltip.is-on');
  eq('hovering a column shows the tooltip', await tip.isVisible(), true);
  const tipText = await tip.innerText();
  check('the tooltip prints the session\'s ratio, counts and verdict', tipText.includes(ts.ratio_10d.toFixed(2)) && tipText.includes(thousands(ts.up4) + ' / ' + thousands(ts.down4)) && tipText.includes('verdict ' + ts.verdict), tipText);
  await p.locator(`#historical-evidence rect[data-hit="${target.session}"]`).click(); await settle(p);
  eq('clicking a published night\'s column makes it current', await nightOf(p), target.session);
  const unpub = F.market.sessions.find((s) => s.basis === 'history');
  await p.locator(`#historical-evidence rect[data-hit="${unpub.date}"]`).hover(); await settle(p, 150);
  check('a session with no publication says so in its tooltip', (await tip.innerText()).includes('no publication'), await tip.innerText());
  await p.locator(`#historical-evidence rect[data-hit="${unpub.date}"]`).click(); await settle(p);
  eq('clicking it moves nothing', await nightOf(p), target.session);
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
  check('Space plays from the stage', (await txt(p, '#historical-evidence [data-find="play"]')) === 'Pause' && (await attr(p, '#historical-evidence [data-find="play"]', 'aria-pressed')) === 'true' && (await stepOf(p)) >= 2, await stepOf(p));
  await p.locator('#historical-evidence [data-find="play"]').click();
  const held = await stepOf(p); await settle(p, 600);
  eq('Pause holds the night', await stepOf(p), held);
  eq('Pause reads Play again', [await txt(p, '#historical-evidence [data-find="play"]'), await attr(p, '#historical-evidence [data-find="play"]', 'aria-pressed')], ['Play', 'false']);
  await p.locator('#historical-evidence [data-find="next"]').focus();
  await p.keyboard.press(' '); await settle(p);
  eq('Space on the Next button steps rather than plays', [await stepOf(p), await txt(p, '#historical-evidence [data-find="play"]')], [held + 1, 'Play']);
  await p.locator('#historical-evidence [data-find-night]').last().click(); await settle(p);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p, 120);
  eq('Play from the last night starts over', await stepOf(p), 1);
  await p.locator('#historical-evidence [data-find="play"]').click(); await settle(p);
  eq('and is paused again', await txt(p, '#historical-evidence [data-find="play"]'), 'Play');

  // ---- 8. the blocks under the replay: the backtest, run 6, the reading
  const L = F.backtest.lookback_130, X = F.backtest.lookback_260, prod = L.gates.production, cf = L.gates.no_regime_gate;
  const strip = await txt(p, '#historical-evidence dl[data-find="backtest-strip"]');
  eq('the backtest strip is four cells', await p.locator('#historical-evidence dl[data-find="backtest-strip"] .sc-stat').count(), 4);
  check('the strip prints the sessions, the tickets and the net R', strip.includes(thousands(L.evaluated.count)) && strip.includes(thousands(prod.tickets)) && strip.includes(rr(prod.settled.sum_r)) && strip.includes(plural(prod.settled.n, 'settled ticket')), strip);
  check('the strip counts the nights by regime', strip.includes(thousands(L.regimes.verdicts.yellow || 0) + ' yellow') && strip.includes(thousands(L.regimes.verdicts.red || 0) + ' red'), strip);
  const rates = await txt(p, '#historical-evidence p[data-find="backtest-rates"]');
  check('the rates line prints the win rate, the mean and the median the summary read', prod.settled.readable === true && rates.includes('Win rate ' + Math.round(prod.settled.win_rate * 100) + '%') && rates.includes('mean ' + rr(prod.settled.avg_r)) && rates.includes('median ' + rr(prod.settled.median_r)), rates);
  check('and the equivalence the shortened lookback passed', rates.includes('equivalence ' + L.lookback.equivalence.status) && rates.includes(plural(L.lookback.equivalence.differences, 'difference')), rates);
  const brows = await rows(p, '#historical-evidence [data-find="backtest-table"]');
  eq('the backtest table has the two blocks, their splits and the exact lookback', brows.length, 2 + Object.keys(cf.by_regime).length + Object.keys(cf.by_grade).length + 2);
  eq('the production row prints its tickets and its sum', [brows[0][1], brows[0][4]], [thousands(prod.tickets), signed(prod.settled.sum_r, 2)]);
  eq('the counterfactual row prints its sum', brows[1][4], signed(cf.settled.sum_r, 2));
  check('a counterfactual split row prints its own numbers', Object.keys(cf.by_regime).sort().every((k, i) => brows[2 + i][0].includes(k) && brows[2 + i][4] === signed(cf.by_regime[k].sum_r, 2)), JSON.stringify(brows.slice(2, 4)));
  const exact = brows[brows.length - 2];
  check('the exact-lookback row prints a dash where the summary read no rate', X.gates.production.settled.avg_r === null && exact[0].includes(plural(X.evaluated.count, 'session')) && exact[5] === '—' && exact[7] === '—' && exact[4] === signed(X.gates.production.settled.sum_r, 2), JSON.stringify(exact));
  const source = await txt(p, '#historical-evidence p[data-find="backtest-source"]');
  check('the source line names both summaries by their digests', source.includes(L.source.sha256.slice(0, 12)) && source.includes(X.source.sha256.slice(0, 12)), source);
  const days = Object.keys(F.run6.sessions).sort(), first = F.run6.sessions[days[0]];
  const r6 = await rows(p, '#historical-evidence [data-find="run6-table"]');
  eq('the run-6 table has one row per session', r6.length, days.length);
  check('the first row prints the published and the fresh ratio', r6[0][1].startsWith(first.original.ratio_10d.toFixed(2)) && r6[0][2] === first.policies.C.ratio_10d.toFixed(2) && r6[0][4].includes(first.policies.C.ratio_10d_bounds.map((v) => v.toFixed(2)).join(' to ')), JSON.stringify(r6[0]));
  const r6facts = await txt(p, '#historical-evidence p[data-find="run6-facts"]');
  check('the run-6 facts name every blocking stock and the download', F.run6.blocking_names.every((n) => r6facts.includes(n)) && r6facts.includes(thousands(F.run6.download.queries_completed) + ' of ' + thousands(F.run6.download.queries_total) + ' queries') && r6facts.includes(thousands(first.partial) + ' symbols'), r6facts);
  const readAs = await p.locator('#historical-evidence ul[data-find="read-as"] > li').evaluateAll((e) => e.map((li) => li.textContent));
  eq('the reading carries the four standing sentences and the file\'s', readAs.length, 4 + F.read_as.length);
  check('every read-as sentence of the file is printed verbatim', F.read_as.every((s) => readAs.includes(s)), JSON.stringify(readAs));
  eq('every report is linked at its served path', await p.locator('#historical-evidence ul[data-find="reports"] a').evaluateAll((e) => e.map((a) => [a.getAttribute('href'), a.textContent])), F.reports.map((r) => [r.path.replace(/^docs\//, ''), r.title]));

  // ---- 9. nothing undefined, nothing open, no errors
  const all = await txt(p, '#historical-evidence');
  check('nothing in the section prints undefined or NaN', !/\bundefined\b|\bNaN\b/.test(all), (all.match(/.{0,40}\b(undefined|NaN)\b.{0,40}/) || [''])[0]);
  eq('the replay opens no dialog', await p.locator('dialog[open]').count(), 0);
  if (shotsDir) { await p.locator('#historical-evidence [data-find-night]').first().click(); await settle(p); await p.locator('#historical-evidence').screenshot({ path: path.join(shotsDir, 'findings-1280-dark.png') }); }
  eq('findings page errors', f.errors, []);
  await f.context.close();

  // ---- 10. phones, both themes: stacked, fitting, the short reference names
  for (const width of [390, 320]) for (const theme of ['dark', 'light']) {
    const n = await load(FULL, width, { height: 844, theme });
    const q = n.page, tag = `${width} ${theme}`;
    eq(`${tag}: the replay is ready`, await ready(q), 'ready');
    check(`${tag}: nothing scrolls sideways`, !(await sideways(q)));
    check(`${tag}: the chart fits its column`, await svgFits(q));
    check(`${tag}: the stage, the index and the caption stack`, await q.evaluate(() => {
      const r = (s) => document.querySelector('#historical-evidence ' + s).getBoundingClientRect();
      return r('.ss-find__side').top >= r('.ss-find__stage').bottom - 1 && r('.ss-find__caption').top >= r('.ss-find__side').bottom - 1;
    }));
    eq(`${tag}: the yellow band is not named on a phone`, await q.locator('#historical-evidence text[data-ref-label="yellow"]').count(), 0);
    check(`${tag}: the red and green lines keep their short names`, (await tc(q, '#historical-evidence text[data-ref-label="red"]')) === 'red below ' + F.market.thresholds.ratio_10d_red.toFixed(1) && (await tc(q, '#historical-evidence text[data-ref-label="green"]')) === 'green above ' + F.market.thresholds.ratio_10d_yellow.toFixed(1));
    await q.locator('#historical-evidence [data-find="next"]').click(); await settle(q);
    check(`${tag}: a step keeps the chart inside its column`, (await stepOf(q)) === 2 && !(await sideways(q)));
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

  // ---- 12. routed controls: the page prints the file and computes nothing
  const routed = (body, status) => async (page) => {
    await fast(page);
    await page.route('**/historical-findings.json*', (route) => route.fulfill({ status: status || 200, contentType: 'application/json', body }));
  };
  const altered = structuredClone(F);
  altered.nights[0].strata.admitted.settled.sum_r = 123.45;
  const a = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(altered)) });
  eq('altered file: the replay is ready', await ready(a.page), 'ready');
  const afx = await facts(a.page);
  check('a changed sum in the file is printed as given, so the page computes nothing', afx.includes('+123.45R in all') && !afx.includes(rr(F.nights[0].strata.admitted.settled.sum_r) + ' in all'), afx);
  check('and the mean beside it is still the file\'s own, not re-derived from the sum', (await pill(a.page)).includes(rr(F.nights[0].strata.admitted.settled.mean_r)), await pill(a.page));
  eq('altered file errors', a.errors, []);
  await a.context.close();
  const e = await load(FULL, 1280, { beforeLoad: routed('boom', 500) });
  eq('a 500 leaves the replay in its error state', await ready(e.page), 'error');
  eq('and says the findings are unavailable', await txt(e.page, HOST + ' p[role="alert"]'), 'The validation findings are unavailable.');
  eq('while the scorecard still renders', (await txt(e.page, '#record-card')).includes('Published model plans'), true);
  eq('and the open model plans still render', await e.page.locator('#hold-rows > *').count(), data.open_plans.length);
  eq('a 500 draws no replay', await e.page.locator(HOST + ' [data-find-root]').count(), 0);
  eq('the only error is the 500 this check served', e.errors.filter((x) => !/500/.test(x)), []);
  await e.context.close();
  const wrong = structuredClone(F); wrong.version = 'historical-findings-v0';
  const v = await load(FULL, 1280, { beforeLoad: routed(JSON.stringify(wrong)) });
  eq('a wrong version leaves the replay in its error state', await ready(v.page), 'error');
  eq('and names the version', await txt(v.page, HOST + ' p[role="alert"]'), 'Unknown findings version.');
  eq('wrong-version errors', v.errors, []);
  await v.context.close();

  // ---- 13. the live record wears no demo note
  const live = await load('/docs/data.json', 1280, { now: LIVE_NOW });
  eq('the live record is not a fixture', await live.page.getAttribute('html', 'data-ss-demo'), 'false');
  eq('live: the replay is ready', await ready(live.page), 'ready');
  eq('live: no demo note', await live.page.locator(HOST + ' p[data-findings-demo]').count(), 0);
  eq('live: every night is listed', await live.page.locator('#historical-evidence [data-find-night]').count(), N);
  eq('live findings errors', live.errors, []);
  await live.context.close();
}
