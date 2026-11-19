/* Fidelity's buy-stop rule beside a BURST ticket, and the band a ticket can
   fill in. A burst ticket's buy stop is the burst session's close
   (src/plan.py burst_plan()), and Fidelity's stated rule is that a buy stop is
   entered above the current market price (knowledge/broker-fidelity.md, item
   2). So the page prints a second labelled broker note directly after the
   part-fill note wherever it prints a burst ticket's order, and never beside
   a setting-up ticket's, whose trigger sits above its last close.

   What this suite holds, on the real page over the pipeline's own fixtures:
   - a burst ticket's first view: the two notes ride under ONE closed native
     disclosure on the action card and in the decision summary's entry, both
     in the DOM, the part-fill note first; beside the order block and the
     model exits they are printed open, in that order;
   - the first screen the fold exists for: with the card at the top of a phone
     screen its Copy order control is on that screen;
   - a copied order, from the card and from the order block, is the printed
     ticket and carries neither note, and so does every text the page writes
     to the clipboard;
   - the plan's fill row is the buy stop up to the limit, read by its own
     value, and the chart's levels table says "entry zone" and that a buy stop
     fills only from its trigger up, on a burst and not on a coil;
   - a disclosure the reader opened stays open when the clock repaints it;
   - a setting-up ticket's page carries no buy-stop note and no disclosure;
   - the next action says what is unconfirmed about Fidelity's ticket, and
     names the burst's buy stop only on a night with a burst ticket;
   - the private handoff's readback shows the note for a bursts-stage draft
     and hides it for a setting-up draft, and its copy carries neither note.
   No broker, provider or network is involved. */
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const PAGE = 'tests/fixtures/page';
const CASH = 'tests/fixtures/cash-preview';
// Thursday 10 Sep 2026, 6:31 PM ET: the evening the page fixtures were made for
const FRESH = '2026-09-10T22:31:00Z';
const usd = (v) => '$' + Math.abs(v).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const constant = (src, name) => src.match(new RegExp('const ' + name + " = '([^']+)';"))[1];

// Every broker note under `scope` that is not under a [hidden] ancestor, in
// document order: [where its container sits, which note, whether it is under
// the one disclosure, what a sighted reader gets, whether it is the text].
const notesOf = (page, scope, want) => page.evaluate(([scope, want]) => [...document.querySelectorAll(scope + ' [data-broker-part-fill], ' + scope + ' [data-broker-buy-stop]')]
  .filter((e) => !e.closest('[hidden]')).map((e) => {
    const fold = e.closest('details[data-broker-notes]');
    const host = (fold || e).parentElement;
    const where = host.matches('.ss-action--burst') ? 'card' : host.matches('.ss-decision__item[data-item="need"]') ? 'need'
      : host.matches('.ss-order--history') ? 'recorded' : host.matches('.ss-order') ? 'order' : host.id === 'orders-table' ? 'sheet'
      : host.closest('#disc-exits') ? 'exits' : host.matches('.ss-action') ? 'bar' : host.matches('[data-handoff-readback]') ? 'handoff' : 'other';
    let collapsed = false;
    for (let a = e.parentElement; a; a = a.parentElement) if (a.tagName === 'DETAILS' && !a.open) collapsed = true;
    const r = e.getBoundingClientRect(), kind = e.hasAttribute('data-broker-buy-stop') ? 'buy-stop' : 'part-fill';
    const inside = !!e.closest('pre, li, .ss-order__terms, button');
    return [where, kind, !!fold, collapsed ? 'collapsed' : r.width > 2 && r.height > 2 && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && !inside ? 'seen' : 'unseen', e.textContent === want[kind]];
  }), [scope, want]);
const row = (where, fold, how) => [[where, 'part-fill', fold, how, true], [where, 'buy-stop', fold, how, true]];
// The clipboard read again until it no longer holds the sentinel written
// before the copy; the sentinel, still there after five seconds, is returned.
const copied = async (page, sentinel) => {
  for (let i = 0; i < 100; i++) {
    const t = await page.evaluate(() => navigator.clipboard.readText());
    if (t !== sentinel) return t;
    await page.waitForTimeout(50);
  }
  return sentinel;
};
// every text the page writes to the clipboard, kept in the tab's session storage
const recordWrites = (page) => page.addInitScript(() => {
  const c = navigator.clipboard; if (!c || !c.writeText) return;
  const write = c.writeText.bind(c);
  c.writeText = (t) => { try { const k = 'ss:clipwrites', a = JSON.parse(sessionStorage.getItem(k) || '[]'); a.push(String(t)); sessionStorage.setItem(k, JSON.stringify(a)); } catch (e) { /* no storage */ } return write(t); };
});
const writesOf = async (page) => (await page.evaluate(() => JSON.parse(sessionStorage.getItem('ss:clipwrites') || '[]'))).filter((t) => !/ sentinel$/.test(t));
const NOTE_WORDS = /Fidelity|SpicyStock’s advice|fills only in part|buy stop or buy stop-limit|entered as written/;

export async function checkBuyStop({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- the buy-stop rule beside a burst ticket, the fill band, and the Broker notes disclosure');
  const app = await readFile(path.join(ROOT, 'docs', 'app.js'), 'utf8'), ui = await readFile(path.join(ROOT, 'docs', 'app-handoff-ui.js'), 'utf8');
  const want = { 'part-fill': constant(app, 'BROKER_PART_FILL'), 'buy-stop': constant(app, 'BROKER_BUY_STOP') };
  eq('the handoff carries the page\'s two texts', [constant(ui, 'BROKER_PART_FILL'), constant(ui, 'BROKER_BUY_STOP')], [want['part-fill'], want['buy-stop']]);
  check('the buy-stop text keeps its two labels and no digit', want['buy-stop'].startsWith('Fidelity’s rule: ') && want['buy-stop'].includes(' SpicyStock’s advice: ') && !/\d/.test(want['buy-stop']), want['buy-stop']);
  const full = JSON.parse(await readFile(path.join(ROOT, PAGE, 'full.json'), 'utf8'));
  const burst = full.bursts.find((b) => (full.trades || []).includes(b.ticker) && b.plan && b.plan.order_json);
  check('the full fixture carries a burst ticket whose buy stop is its close to the cent, so every check below can fail',
    !!burst && burst.plan.order_json.stop_price === burst.plan.entry_ref && Math.abs(burst.plan.entry_ref - burst.close) <= 0.005 + 1e-9 && burst.plan.entry_low < burst.plan.entry_ref && burst.plan.entry_ref < burst.plan.limit,
    burst && [burst.ticker, burst.close, burst.plan.entry_ref, burst.plan.entry_low, burst.plan.limit]);
  if (!burst) return;
  const p = burst.plan;
  if (shotsDir) await mkdir(shotsDir, { recursive: true });

  // ---- a burst ticket's page, as it opens and as the reader opens it
  for (const [width, height, theme] of [[1280, 900, 'dark'], [390, 844, 'light'], [320, 844, 'dark']]) {
    const tag = `${width} ${theme}`;
    const { context, page, errors } = await open(browser, base, `/${PAGE}/full.json`, FRESH, width, { height, theme, lens: 'all', hash: `#/explore/bursts/${burst.ticker}`, beforeLoad: recordWrites });
    try {
      eq(`${tag}: the card offers the order`, await page.locator('#detail .ss-action').getAttribute('data-ticket'), 'order');
      // nothing opened: the card's and the entry's notes under one closed
      // disclosure each, the order block's and the exits' under the closed
      // plan and exit disclosures, the part-fill note first at every place
      eq(`${tag}: as the page opens, each place prints the part-fill note and then the buy-stop note, and none is open on the first view`,
        await notesOf(page, '#detail', want), [...row('card', true, 'collapsed'), ...row('need', true, 'collapsed'), ...row('order', false, 'collapsed'), ...row('exits', false, 'collapsed')]);
      eq(`${tag}: the two disclosures are native, closed, labelled, and hold one of each note`,
        await page.locator('#detail details[data-broker-notes]').evaluateAll((els) => els.map((e) => [e.tagName, e.open, e.querySelector(':scope > summary').textContent, e.querySelectorAll('[data-broker-part-fill]').length, e.querySelectorAll('[data-broker-buy-stop]').length])),
        Array(2).fill(['DETAILS', false, 'Broker notes · Fidelity’s part-fill and buy-stop rules', 1, 1]));
      check(`${tag}: no note's words are drawn on the first view`, !(await page.locator('#detail').innerText()).includes('must be entered at a stop price above the current market price'), 'the buy-stop note is drawn');
      // the first screen the disclosure exists for
      const geom = await page.evaluate(() => {
        const box = (sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { top: Math.round(r.top + scrollY), bottom: Math.round(r.bottom + scrollY), height: Math.round(r.height) }; };
        return { card: box('#detail .ss-action'), copy: box('#detail .ss-action [data-copy]'), fold: box('#detail .ss-action details[data-broker-notes]'), screen: innerHeight, sideways: document.documentElement.scrollWidth > innerWidth };
      });
      console.log(`  ${tag} card ${geom.card.height}px, Copy order ends ${geom.copy.bottom - geom.card.top}px under the card's top, the closed disclosure ${geom.fold.height}px, screen ${geom.screen}px`);
      check(`${tag}: with the card at the top of the screen its Copy order is on that screen`, geom.copy.bottom - geom.card.top <= geom.screen, JSON.stringify(geom));
      // its label wraps to three lines at 320 px; the two notes open are 429 px at 390 and 566 px at 320
      check(`${tag}: the closed disclosure is its label alone, not two notes`, geom.fold.height <= 120 && !geom.sideways, JSON.stringify(geom));
      if (shotsDir) await page.locator('#detail .ss-action').screenshot({ path: path.join(shotsDir, `buystop-card-closed-${width}-${theme}.png`) });

      // the card's Copy order hands over the ticket and neither note
      const pre = (p.order_json && await page.locator('#detail .ss-action pre.ss-order__pre').evaluate((n) => n.textContent)) || '';
      await page.evaluate(() => navigator.clipboard.writeText('card sentinel').catch(() => {}));
      await page.locator('#detail .ss-action [data-copy]').click();
      const fromCard = await copied(page, 'card sentinel');
      eq(`${tag}: the card's Copy order copies the printed ticket`, fromCard, pre);
      check(`${tag}: and the ticket copied names the buy stop and the limit and carries neither broker note`, fromCard.includes('stop ' + usd(p.entry_ref)) && fromCard.includes('limit ' + usd(p.limit)) && !NOTE_WORDS.test(fromCard), fromCard);

      // the reader opens the card's disclosure: by the keyboard, natively
      await page.locator('#detail .ss-action details[data-broker-notes] > summary').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelector('#detail .ss-action details[data-broker-notes]').open);
      eq(`${tag}: opened, the card shows the part-fill note and then the buy-stop note, above Copy order; the entry's stay closed`,
        (await notesOf(page, '#detail', want)).slice(0, 4), [...row('card', true, 'seen'), ...row('need', true, 'collapsed')]);
      eq(`${tag}: the opened notes sit between the card's terms and its controls`, await page.evaluate(() => {
        const f = document.querySelector('#detail .ss-action details[data-broker-notes]'), terms = document.querySelector('#detail .ss-action .ss-action__terms'), ctl = document.querySelector('#detail .ss-action .ss-action__controls');
        const notes = [...f.querySelectorAll('[data-broker-part-fill], [data-broker-buy-stop]')].map((n) => n.getBoundingClientRect());
        return [f.parentElement === ctl.parentElement, terms.getBoundingClientRect().bottom <= notes[0].top, notes[0].bottom <= notes[1].top, notes[1].bottom <= ctl.getBoundingClientRect().top, document.documentElement.scrollWidth > innerWidth];
      }), [true, true, true, true, false]);
      const ink = await page.evaluate(() => [...document.querySelectorAll('#detail .ss-action [data-broker-part-fill], #detail .ss-action [data-broker-buy-stop], #detail .ss-action .ss-action__sizing')].map((e) => getComputedStyle(e).color));
      check(`${tag}: both notes are drawn in the hint's colour`, ink.length === 3 && ink.every((c) => c === ink[0]), ink);
      if (shotsDir) await page.locator('#detail .ss-action').screenshot({ path: path.join(shotsDir, `buystop-card-open-${width}-${theme}.png`) });

      // the plan disclosure: the fill row, the order block and its notes
      await page.locator('#detail .ss-action [data-open="disc-plan"]').click();
      await page.waitForFunction(() => document.getElementById('disc-plan').open);
      const fill = await page.locator('#disc-plan .sc-facts > div').filter({ has: page.locator('dt', { hasText: /^ticket fills$/ }) }).evaluateAll((rows) => rows.map((r) => { const dd = r.querySelector('dd'), k = dd.cloneNode(true); k.querySelectorAll('small').forEach((n) => n.remove()); return [k.textContent.trim(), (dd.querySelector('small') || {}).textContent || '']; }));
      eq(`${tag}: one row says where the ticket fills, by its own value: the buy stop up to the limit`, fill.map((r) => r[0]), [usd(p.entry_ref) + ' – ' + usd(p.limit)]);
      check(`${tag}: and its sentence names the buy stop as the burst close and says the order buys nothing under it`,
        fill.length === 1 && fill[0][1].startsWith(p.entry_window + ' · a buy stop at ' + usd(p.entry_ref) + ' (the burst close), limit ' + usd(p.limit) + ' · under the buy stop the order waits and buys nothing'), fill.length && fill[0][1]);
      eq(`${tag}: no row is labelled buy, and the skip line keeps its own row`,
        await page.locator('#disc-plan .sc-facts > div dt').evaluateAll((dts, lo) => [dts.filter((d) => d.textContent === 'buy').length, dts.filter((d) => d.textContent === 'skip if it opens below').map((d) => { const k = d.nextElementSibling.cloneNode(true); k.querySelectorAll('small').forEach((n) => n.remove()); return k.textContent.trim(); })], null),
        [0, [usd(p.skip_if_open_below)]]);
      eq(`${tag}: beside the order block the two notes are printed open, after the ticket's terms and never inside them`,
        (await notesOf(page, '#disc-plan', want)), row('order', false, 'seen'));
      eq(`${tag}: the order block's notes follow its <pre> and its terms list, the part-fill note first`, await page.evaluate(() => {
        const b = document.querySelector('#disc-plan .ss-order:not(.ss-order--history)'), kids = [...b.children];
        const i = (sel) => kids.findIndex((k) => k.matches(sel));
        return [i('pre[data-order]') < i('[data-broker-part-fill]'), i('.ss-order__terms') < i('[data-broker-part-fill]'), i('[data-broker-buy-stop]') === i('[data-broker-part-fill]') + 1, kids.filter((k) => k.matches('[data-broker-buy-stop]')).length,
          [...b.querySelectorAll('.ss-order__terms li, pre')].some((n) => /Fidelity/.test(n.textContent))];
      }), [true, true, true, 1, false]);
      const orderPre = await page.locator('#disc-plan pre[data-order]').evaluate((n) => n.textContent);
      await page.evaluate(() => navigator.clipboard.writeText('order sentinel').catch(() => {}));
      await page.locator('#disc-plan .ss-order [data-copy]').click();
      const fromOrder = await copied(page, 'order sentinel');
      eq(`${tag}: the order block's Copy copies the printed ticket`, fromOrder, orderPre);
      check(`${tag}: and carries neither broker note`, fromOrder.length > 0 && !NOTE_WORDS.test(fromOrder), fromOrder);
      if (shotsDir) await page.locator('#disc-plan').screenshot({ path: path.join(shotsDir, `buystop-plan-${width}-${theme}.png`) });

      // the model exits: the dated schedule, then the two notes
      await page.evaluate(() => { document.getElementById('disc-exits').open = true; });
      eq(`${tag}: under the dated schedule the two notes are printed open`, await notesOf(page, '#disc-exits', want), row('exits', false, 'seen'));
      eq(`${tag}: directly after the timeline, the part-fill note and then the buy-stop note`, await page.evaluate(() => {
        const t = document.querySelector('#disc-exits ol.sc-timeline'), a = t.nextElementSibling, b = a && a.nextElementSibling;
        return [!!(a && a.matches('[data-broker-part-fill]')), !!(b && b.matches('[data-broker-buy-stop]'))];
      }), [true, true]);

      // the chart's levels table: the zone is named for what it is, and says
      // a buy stop fills only from its trigger up
      const levels = await page.locator('#detail [data-sc-twin=levels] tbody tr').evaluateAll((rows) => rows.map((r) => [...r.children].map((c) => c.textContent)));
      const zone = levels.filter((r) => /zone/.test(r[0]));
      eq(`${tag}: the levels table names the entry zone, from the skip line to the limit`, zone.map((r) => [r[0], r[1]]), [['entry zone (to the limit)', usd(p.entry_low) + ' – ' + usd(p.entry_high)]]);
      check(`${tag}: and says a buy stop fills only from the trigger up`, zone.length === 1 && zone[0][2].endsWith(' · a buy stop fills only from the ' + usd(p.entry_ref) + ' trigger up'), zone.length && zone[0][2]);
      check(`${tag}: nothing in the chart or its table says buy zone`, !/buy zone/i.test(await page.locator('#detail .ss-chart-panel').evaluate((n) => n.textContent)), 'buy zone');

      // the tickets sheet: its orders are burst tickets, so both notes follow it
      await page.evaluate(() => { location.hash = '#/explore'; });
      await page.waitForTimeout(150);
      await page.evaluate(() => { document.getElementById('orders').open = true; });
      eq(`${tag}: under the tickets sheet the part-fill note and then the buy-stop note, once each`, await notesOf(page, '#orders-table', want), row('sheet', false, 'seen'));
      eq(`${tag}: both directly after the table`, await page.evaluate(() => { const t = document.getElementById('order-sheet'), a = t.nextElementSibling, b = a && a.nextElementSibling; return [!!(a && a.matches('[data-broker-part-fill]')), !!(b && b.matches('[data-broker-buy-stop]'))]; }), [true, true]);

      // the next action: what is written, what Fidelity is known to do, what is unconfirmed
      const next = await page.locator('#next-p').innerText();
      check(`${tag}: the next action says the stop is written as part of the order and what is unconfirmed, naming the burst's buy stop`,
        next.includes('Its sell stop is written as part of the order (OTO): Fidelity releases an OTO stop only when the buy fills in full, and whether Fidelity’s ticket accepts this OTO, or a burst ticket’s buy stop at its last close, is unconfirmed. Cancel an unfilled entry by the end of the ')
        && !next.includes('is part of the order (OTO), and Fidelity releases that stop'), next);

      const writes = await writesOf(page);
      eq(`${tag}: every text the page wrote to the clipboard was the ticket, and none carried a broker note`, [writes.length, writes.filter((t) => t !== pre).length, writes.filter((t) => NOTE_WORDS.test(t)).length], [2, 0, 0]);
      eq(`${tag}: page errors`, errors.slice(), []);
    } finally { await context.close(); }
  }

  // ---- a disclosure the reader opened stays open when the clock repaints it:
  // the window ends, the decision summary is rebuilt, and the entry's notes
  // are still open (the card, which then offers no order, prints none)
  {
    const tm = full.run.timing;
    const { context, page, errors } = await open(browser, base, `/${PAGE}/full.json`, null, 1280, { lens: 'all', hash: `#/explore/bursts/${burst.ticker}` });
    try {
      const at = (iso) => page.evaluate((iso) => {
        if (!window.__real) { const Real = window.__real = Date; function Fake(...a) { return a.length ? new Real(...a) : new Real(window.__fake); } Fake.now = () => window.__fake; Fake.parse = Real.parse; Fake.UTC = Real.UTC; Fake.prototype = Real.prototype; window.Date = Fake; }
        window.__fake = new window.__real(iso).getTime();
        return [window.SCStock.reclock(), document.documentElement.getAttribute('data-ss-window')];
      }, iso);
      const inside = new Date(new Date(tm.opens_at).getTime() + 10 * 60000).toISOString(), after = new Date(new Date(tm.cutoff_at).getTime() + 60 * 60000).toISOString();
      eq('left open: inside the window the card offers the order', [(await at(inside))[1], await page.locator('#detail .ss-action').getAttribute('data-ticket')], ['open', 'order']);
      await page.evaluate(() => { document.querySelectorAll('#detail details[data-broker-notes]').forEach((d) => { d.open = true; d.setAttribute('data-was', 'here'); }); });
      eq('left open: the reader opens both disclosures', (await notesOf(page, '#detail', want)).slice(0, 4), [...row('card', true, 'seen'), ...row('need', true, 'seen')]);
      eq('left open: the clock crosses the cutoff', await at(after), [true, 'ended']);
      eq('left open: the card offers no order and prints no note; the entry\'s disclosure was rebuilt and is still open',
        [await page.locator('#detail .ss-action').getAttribute('data-ticket'), await page.locator('#detail .ss-action [data-broker-part-fill], #detail .ss-action [data-broker-buy-stop]').count(),
          await page.locator('#detail details[data-broker-notes]').evaluateAll((els) => els.map((e) => [e.parentElement.getAttribute('data-item'), e.open, e.hasAttribute('data-was')]))],
        ['blocked', 0, [['need', true, false]]]);
      eq('left open: page errors', errors.slice(), []);
    } finally { await context.close(); }
  }

  // ---- a setting-up ticket: its trigger sits above its last close, so no
  // buy-stop note and no disclosure anywhere on its page
  for (const variant of ['degraded', 'notrade']) {
    const data = JSON.parse(await readFile(path.join(ROOT, PAGE, variant + '.json'), 'utf8'));
    const coil = ((data.watchlist || {}).top || []).find((r) => r.plan && r.plan.order_json);
    const burstTickets = (data.trades || []).filter((t) => { const b = data.bursts.find((x) => x.ticker === t); return b && b.plan && b.plan.order_json; }).length;
    check(`${variant}: the night carries a setting-up ticket whose trigger is over its close, and no burst ticket, so the checks below can fail`,
      !!coil && coil.plan.trigger > coil.close && coil.plan.order_json.stop_price === coil.plan.trigger && burstTickets === 0, coil && [coil.ticker, coil.close, coil.plan.trigger, burstTickets]);
    if (!coil) continue;
    for (const [width, height, theme] of [[1280, 900, 'dark'], [390, 844, 'light']]) {
      const tag = `${variant} ${coil.ticker} ${width} ${theme}`;
      const { context, page, errors } = await open(browser, base, `/${PAGE}/${variant}.json`, FRESH, width, { height, theme, lens: 'all', hash: `#/explore/setting-up/${coil.ticker}` });
      try {
        await page.evaluate(() => document.querySelectorAll('#detail details, #orders').forEach((d) => { d.open = true; }));
        const got = await notesOf(page, 'body', want);
        eq(`${tag}: the part-fill note beside the bar's order line, the order block and the exits, so its absence below is the stage's`,
          got.filter((n) => n[1] === 'part-fill').map((n) => [n[0], n[3], n[4]]), [['bar', 'seen', true], ['order', 'seen', true], ['exits', 'seen', true]]);
        // the one buy-stop note in the document is the private handoff's,
        // built once in the Morning desk and hidden until a burst draft is chosen
        eq(`${tag}: no buy-stop note is shown, the only one in the document is the desk's hidden one, there is no Broker notes disclosure, and none of its words are drawn anywhere on the page`,
          [got.filter((n) => n[1] === 'buy-stop').length, await page.locator('[data-broker-buy-stop]').evaluateAll((els) => els.map((e) => [!!e.closest('#morning-desk'), !!e.closest('[hidden]')])), await page.locator('details[data-broker-notes]').count(),
            (await page.evaluate(() => document.body.innerText)).includes('must be entered at a stop price above the current market price')], [0, [[true, true]], 0, false]);
        const next = await page.locator('#next-p').innerText();
        check(`${tag}: the next action says the OTO's acceptance is unconfirmed and names no burst ticket`,
          next.includes('and whether Fidelity’s ticket accepts this OTO is unconfirmed. Cancel an unfilled entry') && !/burst ticket/.test(next), next);
        // a coil's zone starts at its trigger: the levels table adds no trigger-up sentence
        const zone = (await page.locator('#detail [data-sc-twin=levels] tbody tr').evaluateAll((rows) => rows.map((r) => [...r.children].map((c) => c.textContent)))).filter((r) => /zone/.test(r[0]));
        eq(`${tag}: the levels table names the entry zone from the trigger to the limit, and adds no trigger-up sentence`,
          zone.map((r) => [r[0], r[1], / trigger up/.test(r[2])]), [['entry zone (to the limit)', usd(coil.plan.trigger) + ' – ' + usd(coil.plan.limit), false]]);
        eq(`${tag}: page errors`, errors.slice(), []);
      } finally { await context.close(); }
    }
  }

  // ---- the other doors to a setting-up ticket's order: a comparison of two
  // setting-up candidates, a saved setup and an archived original each print
  // the part-fill note beside the order line and no buy-stop note. The
  // degraded night carries one setting-up stock, so the comparison's second
  // is a labelled in-memory copy of it, served at the fixture's own URL.
  {
    const deg = JSON.parse(await readFile(path.join(ROOT, PAGE, 'degraded.json'), 'utf8'));
    const coil = deg.watchlist.top.find((r) => r.plan && r.plan.order_json);
    const twin = { ...structuredClone(coil), ticker: 'TWIN', name: 'Offline copy of ' + coil.ticker + ' for a two-ticket comparison', rank: 9 };
    twin.plan.ticker = 'TWIN'; twin.plan.order_json.symbol = 'TWIN'; twin.plan.order_json.then.symbol = 'TWIN';
    twin.plan.order_line = twin.plan.order_line.replaceAll(coil.ticker, 'TWIN');
    const two = structuredClone(deg); two.watchlist.top.push(twin);
    const { context, page, errors } = await open(browser, base, `/${PAGE}/degraded.json`, FRESH, 1280, { lens: 'all', hash: `#/explore/setting-up/${coil.ticker}`,
      beforeLoad: (page) => page.route(`**/${PAGE}/degraded.json`, (route) => route.fulfill({ json: two })) });
    try {
      await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${coil.ticker}"]) .ss-pin`);
      await page.click('#pick-list .ss-pick-item:has(.ss-pick[data-ticker="TWIN"]) .ss-pin'); await page.waitForTimeout(200);
      await page.click('#compare-open'); await page.waitForTimeout(500);
      const ticketRow = await page.locator('#compare-table tr[data-fact="ticket"]').innerText();
      check('comparison of two setting-up tickets: the ticket row prints an order line, so the notes below can fail', ticketRow.includes('OTO') && ticketRow.includes(coil.ticker), ticketRow);
      eq('comparison of two setting-up tickets: the part-fill note under the facts and no buy-stop note',
        await page.locator('#compare [data-broker-part-fill], #compare [data-broker-buy-stop]').evaluateAll((els) => els.map((e) => [e.hasAttribute('data-broker-buy-stop') ? 'buy-stop' : 'part-fill', !!(e.previousElementSibling && e.previousElementSibling.matches('.ss-compare__facts'))])),
        [['part-fill', true]]);
      await page.click('#compare-close'); await page.waitForTimeout(200);

      // a saved setting-up ticket: its archived order with the part-fill note alone
      await page.click('#detail .ss-follow button[data-follow-action="add"]');
      await page.waitForFunction(() => document.querySelector('#detail .ss-follow').getAttribute('data-follow') === 'following');
      await page.evaluate(() => { location.hash = '#/setups'; });
      await page.locator(`#following .ss-followed[data-ticker="${coil.ticker}"] [data-open-saved]`).click();
      await page.locator('#saved [data-archived-order]').waitFor();
      eq('saved setting-up ticket: its archived order carries the part-fill note after the instruction and no buy-stop note',
        await page.locator('#saved [data-archived-order]').evaluate((box) => [...box.querySelectorAll('[data-broker-part-fill], [data-broker-buy-stop]')].map((e) => e.hasAttribute('data-broker-buy-stop') ? 'buy-stop' : 'part-fill')), ['part-fill']);
      await page.click('#saved-close'); await page.waitForTimeout(250);
      eq('setting-up doors: page errors', errors.slice(), []);
    } finally { await context.close(); }

    // an archived original that was a setting-up ticket, from a synthetic
    // archive of the degraded night served under the digests the page checks
    const { createHash } = await import('node:crypto');
    const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
    const src = 'c01c01'.padEnd(40, '0');
    const file = `anticipation-${coil.ticker}.json`;
    const files = { 'record.json': Buffer.from(JSON.stringify({ ...deg, bursts: [] })), [file]: Buffer.from(JSON.stringify({ kind: 'anticipation', quiet: false, row: coil, source: src })) };
    const archive = { version: 1, as_of: deg.run.session, days: 21, dates: [deg.run.session],
      records: { [src]: { session: deg.run.session, published_at: deg.run.published_at, context_sha256: sha(files['record.json']), rules_version: deg.app.rules_version } },
      entries: [{ ticker: coil.ticker, kind: 'anticipation', grade: null, scan: null, source: src, path: `${src}/${file}`, sha256: sha(files[file]), chart: true }] };
    const old = await open(browser, base, `/${PAGE}/full.json`, '2026-09-15T22:31:00Z', 1280, { hash: '#/setups' });
    try {
      await old.page.route('**/history/index.json', (route) => route.fulfill({ json: archive }));
      await old.page.route(`**/history/${src}/*.json`, async (route) => {
        const name = new URL(route.request().url()).pathname.split('/').at(-1);
        await route.fulfill(files[name] ? { contentType: 'application/json', body: files[name] } : { status: 404 });
      });
      await old.page.locator('#earlier-setups summary').click();
      await old.page.locator('#history-ticker').fill(coil.ticker);
      await old.page.locator('#history-search button').click();
      await old.page.locator(`[data-history-inspect="${src}"]`).click();
      await old.page.locator('[data-history-save]').waitFor();
      const line = await old.page.locator('#history-results [data-original-status]').innerText();
      check('archived setting-up ticket: its status sentence prints its order line, so the notes below can fail', line.includes(coil.plan.order_line), line);
      eq('archived setting-up ticket: the part-fill note follows its status sentence and no buy-stop note does',
        await old.page.locator('#history-results [data-broker-part-fill], #history-results [data-broker-buy-stop]').evaluateAll((els) => els.map((e) => [e.hasAttribute('data-broker-buy-stop') ? 'buy-stop' : 'part-fill', !!(e.previousElementSibling && e.previousElementSibling.matches('[data-original-status]'))])),
        [['part-fill', true]]);
      eq('archived setting-up ticket: page errors', old.errors.slice(), []);
    } finally { await old.context.close(); }
  }

  // ---- "the burst close" is said only of a buy stop that is the row's own
  // close to the cent: a close a fraction of a cent off it is the close, and
  // a row whose recorded close is another price is not called one
  {
    const multiple = JSON.parse(await readFile(path.join(ROOT, CASH, 'publication-multiple.json'), 'utf8'));
    const odd = multiple.bursts.find((b) => (multiple.trades || []).includes(b.ticker) && b.plan && b.plan.order_json);
    check('the cash fixture\'s burst ticket closes a fraction of a cent off its buy stop, so the wording below can fail',
      !!odd && odd.close !== odd.plan.entry_ref && Math.abs(odd.close - odd.plan.entry_ref) <= 0.005 + 1e-9, odd && [odd.close, odd.plan.entry_ref]);
    const fillRow = async (page) => { await page.evaluate(() => { document.getElementById('disc-plan').open = true; }); return page.locator('#disc-plan .sc-facts > div').filter({ has: page.locator('dt', { hasText: /^ticket fills$/ }) }).first().innerText(); };
    if (odd) {
      const a = await open(browser, base, `/${CASH}/publication-multiple.json`, '2026-09-11T13:35:00Z', 1280, { lens: 'all', hash: `#/explore/bursts/${odd.ticker}`,
        beforeLoad: (page) => page.route('**/morning.json', (route) => route.fulfill({ status: 404, body: 'not found' })) });
      try {
        const got = await fillRow(a.page);
        check('a buy stop that is the close to the cent is called the burst close', got.includes('a buy stop at ' + usd(odd.plan.entry_ref) + ' (the burst close), limit ' + usd(odd.plan.limit)), got);
      } finally { await a.context.close(); }
    }
    const moved = structuredClone(full); moved.bursts.find((b) => b.ticker === burst.ticker).close = +(burst.close + 1).toFixed(2);
    const b = await open(browser, base, `/${PAGE}/full.json`, FRESH, 1280, { lens: 'all', hash: `#/explore/bursts/${burst.ticker}`,
      beforeLoad: (page) => page.route(`**/${PAGE}/full.json`, (route) => route.fulfill({ json: moved })) });
    try {
      const got = await fillRow(b.page);
      check('a buy stop that is not the row\'s recorded close is not called the burst close, and the row still names it and the limit',
        !got.includes('the burst close') && got.includes('a buy stop at ' + usd(p.entry_ref) + ', limit ' + usd(p.limit) + ' · under the buy stop the order waits and buys nothing'), got);
    } finally { await b.context.close(); }
  }

  // ---- the private handoff: a bursts-stage draft's readback shows the note
  // after the part-fill note; a setting-up draft's hides it; the copied
  // readback carries neither
  {
    const sidecar = await readFile(path.join(ROOT, CASH, 'observed-multiple.json'), 'utf8');
    for (const [width, theme] of [[390, 'light'], [1280, 'dark']]) {
      const tag = `handoff ${width} ${theme}`;
      const { context, page, errors } = await open(browser, base, `/${CASH}/publication-multiple.json`, '2026-09-11T13:35:00Z', width, {
        theme, hash: '#/explore/setting-up/COIL', reducedMotion: 'reduce', beforeLoad: async (page) => {
          await recordWrites(page);
          await page.route('**/morning.json', (route) => route.fulfill({ contentType: 'application/json', body: sidecar }));
        } });
      try {
        await page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.observations.facts().state));
        await page.locator('#morning-open').click();
        await page.locator('.ss-morning__prep > summary').click();
        const prepare = async (plan, quantity, n) => {
          await page.locator('#morning-preview-plan').selectOption(plan);
          await page.locator('#morning-cash').fill('2000'); await page.locator('#morning-preview-fees').fill('1'); await page.locator('#morning-preview-quantity').fill(quantity);
          await page.locator('[data-handoff-prepare]').click();
          await page.waitForFunction((n) => SCStock.handoff.list().length === n, n);
        };
        const choose = async (ticker) => {
          const id = (await page.evaluate(() => SCStock.handoff.list())).find((item) => item.plan.ticker === ticker).id;
          await page.locator('#handoff-select').selectOption(id);
          await page.waitForFunction((t) => document.querySelector('#handoff-title').textContent.startsWith(t + ' '), ticker);
        };
        // [the note's text, its place: after the part-fill note and before the readback's <pre>, shown or hidden, drawn]
        const readback = () => page.locator('#morning-desk [data-broker-buy-stop]').evaluateAll((els) => els.map((e) => {
          const b = e.previousElementSibling; let pre = e.nextElementSibling; while (pre && !pre.matches('pre[data-handoff-text]')) pre = pre.nextElementSibling;
          const r = e.getBoundingClientRect();
          return [e.textContent, e.parentElement.matches('[data-handoff-readback]') && !!(b && b.matches('[data-broker-part-fill]')) && !!pre, e.hidden, r.width > 2 && r.height > 2];
        }));
        await prepare('setting-up:COIL', '2', 1);
        await page.locator('[data-handoff-readback] > summary').click();
        eq(`${tag}: a setting-up draft's readback keeps the part-fill note and hides the buy-stop note`,
          [await page.locator('#morning-desk [data-broker-part-fill]').evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return !e.hidden && r.height > 2; })), await readback()],
          [[true], [[want['buy-stop'], true, true, false]]]);
        await prepare('bursts:AAPL', '1', 2);
        await choose('AAPL');
        eq(`${tag}: the draft chosen is the burst's`, await page.evaluate(() => SCStock.handoff.list().filter((i) => document.querySelector('#handoff-title').textContent.startsWith(i.plan.ticker + ' ')).map((i) => [i.plan.ticker, i.plan.stage])), [['AAPL', 'bursts']]);
        eq(`${tag}: a bursts-stage draft's readback shows the buy-stop note, once, directly after the part-fill note and before the readback`, await readback(), [[want['buy-stop'], true, false, true]]);
        if (shotsDir) {
          // the desk is a dialog with its own scroller: bring the notes to the top of it and shoot the screen
          await page.locator('#morning-desk [data-broker-part-fill]').evaluate((n) => n.scrollIntoView({ block: 'start' }));
          await page.screenshot({ path: path.join(shotsDir, `buystop-handoff-${width}-${theme}.png`) });
        }
        const printed = await page.locator('[data-handoff-text]').textContent();
        await page.evaluate(() => navigator.clipboard.writeText('readback sentinel').catch(() => {}));
        await page.locator('[data-handoff-copy]').click();
        const clip = await copied(page, 'readback sentinel');
        eq(`${tag}: the copied readback is the printed readback`, clip, printed);
        check(`${tag}: it names the burst draft and carries neither broker note`, /BUY 1 AAPL/.test(clip) && !NOTE_WORDS.test(clip), clip.slice(0, 240));
        await choose('COIL');
        eq(`${tag}: back on the setting-up draft the buy-stop note is hidden again`, (await readback()).map((r) => [r[2], r[3]]), [[true, false]]);
        const writes = await writesOf(page);
        eq(`${tag}: every text the page wrote to the clipboard was a readback, and none carried a broker note`, [writes.length, writes.filter((t) => NOTE_WORDS.test(t)).length], [1, 0]);
        eq(`${tag}: page errors`, [...errors], []);
      } finally { await context.close(); }
    }
  }
}
