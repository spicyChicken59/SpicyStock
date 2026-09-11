#!/usr/bin/env node
/* Open docs/index.html against every fixture the pipeline generated and read
   the page back through a real browser: the status chip, the cover, the
   trade cards and their tickets, the open plans, the alerts, the scan matrix,
   the scorecard, the next-action box -- each compared with the record the
   page was handed, never with the page's own source. Then the two states no
   fixture can carry: a record viewed days later (stale) and no record at all.

     node tools/page_smoke.mjs                # every check, no screenshots
     node tools/page_smoke.mjs --shots DIR    # also PNGs at 1280 and 390 px, dark and light

   Exit 1 on any failed check or any page error (a console error, an uncaught
   exception, a failed request that is not a chart PNG or a Google font).
   Needs playwright (npm install --no-save playwright) and its chromium. */
import { createServer } from 'node:http';
import { readFile, stat, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'page');
const VARIANTS = ['full', 'degraded', 'notrade', 'yellow', 'red', 'closed'];
// The instant every fixture was generated for: Thursday 10 Sep 2026, 6:31 PM ET.
const FRESH_NOW = '2026-09-10T22:31:00Z';
const PENDING_NOW = '2026-09-11T20:30:00Z';   // Friday 4:30 PM ET, before the run
const STALE1_NOW = '2026-09-12T14:00:00Z';    // Saturday: Friday's run never came
const STALE2_NOW = '2026-09-16T14:00:00Z';    // Wednesday: four sessions behind
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };

const args = process.argv.slice(2);
const shotsDir = args.includes('--shots') ? args[args.indexOf('--shots') + 1] : null;

let checks = 0, failures = 0;
function check(name, ok, detail) {
  checks++;
  if (!ok) { failures++; console.log(`  FAIL  ${name}${detail === undefined ? '' : ' -- ' + detail}`); }
}
const eq = (name, got, want) => check(name, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);

async function serve() {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    let file = path.join(ROOT, decodeURIComponent(url.pathname));
    try {
      if ((await stat(file)).isDirectory()) file = path.join(file, 'index.html');
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      res.end(body);
    } catch (e) {
      res.writeHead(404); res.end('not found');
    }
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  return { server, base: `http://127.0.0.1:${server.address().port}` };
}

const CUT_WORDS = { withheld: 'ticket withheld', slot_cap: 'beyond the slot cap', equity: 'beyond the configured equity', no_shares: 'no whole share', no_new_longs: 'no new longs' };

async function open(browser, base, dataUrl, now, width, theme) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme || 'dark', permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage();
  const errors = [], aborted = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  // A chart PNG the fixture names but no run rendered, the Google fonts (the
  // system declares a fallback stack) and the optional run-log fetch to the
  // GitHub API are the three requests this page may lose offline; the console
  // reports each as one "Failed to load resource", matched off below.
  const exempt = (u) => /\/charts\/[A-Z.]+\.png$/.test(u) || /fonts\.g(oogleapis|static)\.com/.test(u) || /api\.github\.com/.test(u);
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('requestfailed', (r) => {
    const u = r.url();
    if (exempt(u)) { aborted.push(u); return; }
    errors.push('request failed: ' + u + ' ' + (r.failure() || {}).errorText);
  });
  page.on('response', (r) => { if (r.status() >= 400 && exempt(r.url())) aborted.push(r.url()); });
  await page.addInitScript(({ dataUrl, now, theme }) => {
    window.SCStock = { dataUrl, now };
    if (theme) try { localStorage.setItem('sc-theme', theme); } catch (e) { /* no storage */ }
  }, { dataUrl, now, theme });
  await page.goto(base + '/docs/index.html', { waitUntil: 'load' });
  await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'), null, { timeout: 15000 });
  await page.waitForTimeout(250);
  return { context, page, errors: new Proxy(errors, { get(target, prop) { return prop === 'length' || typeof target[prop] !== 'function' ? settle(target, aborted)[prop] : target[prop].bind(settle(target, aborted)); } }), aborted };
}
// the console's anonymous load failures, one per exempt request, are not errors
function settle(errors, aborted) {
  let budget = aborted.length;
  return errors.filter((e) => { if (/^console: Failed to load resource/.test(e) && budget > 0) { budget--; return false; } return true; });
}

const text = (page, sel) => page.locator(sel).first().innerText();
const count = (page, sel) => page.locator(sel).count();
const usd = (v, dec = 2) => (v < 0 ? '−' : '') + '$' + Math.abs(v).toFixed(dec).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

async function checkVariant(browser, base, variant, data) {
  console.log(`-- ${variant}`);
  const { context, page, errors, aborted } = await open(browser, base, `/tests/fixtures/page/${variant}.json`, FRESH_NOW, 1280);
  const run = data.run, byTicker = Object.fromEntries(data.bursts.map((b) => [b.ticker, b]));
  const trades = data.trades.map((t) => byTicker[t]);

  // status: the one thing the page computes
  const chip = await text(page, '#status-slot .sc-chip');
  if (variant === 'closed') eq(`${variant} chip`, chip, 'market closed');
  else if (run.status === 'degraded') check(`${variant} chip says degraded`, /^degraded/.test(chip), chip);
  else check(`${variant} chip says fresh`, /^fresh/.test(chip), chip);
  eq(`${variant} rendered state`, await page.getAttribute('html', 'data-ss-rendered'),
    variant === 'closed' ? 'closed' : run.status === 'degraded' ? 'degraded' : 'fresh');
  if (run.status === 'degraded') {
    const line = await text(page, '#status-line');
    for (const p of run.problems) check(`${variant} names problem ${p.kind}`, line.includes(SENTENCES[p.kind].slice(0, 30)), line);
    check(`${variant} never prints the recorded message`, !line.includes(run.problems[0].message), line);
  }

  // cover
  eq(`${variant} h1`, await text(page, '#cover-h1'), data.cover.h1);
  eq(`${variant} dek`, await text(page, '#cover-dek'), data.cover.dek);
  eq(`${variant} title`, await page.title(), 'SpicyStock · ' + data.cover.h1);
  eq(`${variant} action`, await text(page, '#cover-action'), data.cover.action_label);
  const meta = await text(page, '#cover-meta');
  check(`${variant} cover names the universe size`, meta.includes(String(run.universe.size).replace(/\B(?=(\d{3})+(?!\d))/g, ',')), meta);
  check(`${variant} cover names Bonde's median night`, meta.includes('239'), meta);

  // strip
  const strip = await text(page, '#run-strip');
  check(`${variant} strip carries the graded counts`, strip.includes(`${run.graded.a} A · ${run.graded.a_plus} A+`), strip);
  check(`${variant} strip carries the reads`, strip.includes(`${run.reads.done} of ${run.reads.requested} read`), strip);
  check(`${variant} strip carries the email state`, strip.includes('email ' + run.email), strip);

  // breadth
  const regime = await text(page, '#regime');
  check(`${variant} regime chip`, regime.includes(data.breadth.regime.verdict.toUpperCase()), regime);
  for (const r of data.breadth.regime.reasons.slice(0, 2)) check(`${variant} regime reason printed`, regime.includes(r), r);
  eq(`${variant} breadth deck has four stats`, await count(page, '#breadth-deck .sc-stat'), 4);
  const deck = await text(page, '#breadth-deck');
  check(`${variant} up-4 count printed`, deck.includes(String(data.breadth.up4)), deck);
  eq(`${variant} ratio chart rows`, await count(page, '#ratio-chart tbody tr'), data.breadth.history.length);
  eq(`${variant} three fact cards`, await count(page, '#breadth-facts .sc-card'), 3);
  const breadthText = (await text(page, '#breadth-facts')) + '\n' + (await text(page, '#ratio-chart'));
  for (const n of data.breadth.notes) check(`${variant} note ${n.key} printed`, breadthText.includes(n.text), n.key);

  // tomorrow: a card per A-quality burst with a plan -- the trades, then the ones beyond the cap
  const beyondCards = data.beyond_cap.map((t) => byTicker[t]).filter((b) => b && b.plan);
  eq(`${variant} trade cards`, await count(page, '#trades article.ss-trade'), trades.length + beyondCards.length);
  const target = data.cover.action_target;
  check(`${variant} cover action target exists`, (await page.locator(target).count()) === 1, target);
  for (const b of trades.concat(beyondCards)) {
    const card = page.locator(`#trade-${b.ticker}`);
    const body = await card.innerText();
    check(`${variant} ${b.ticker} grade chip`, body.includes(b.grade + ' · ' + b.score.toFixed(1)), body.slice(0, 200));
    check(`${variant} ${b.ticker} buy zone`, body.includes(usd(b.plan.entry_low) + ' – ' + usd(b.plan.entry_high)), 'zone');
    check(`${variant} ${b.ticker} stop`, body.includes(usd(b.plan.stop)), 'stop');
    check(`${variant} ${b.ticker} shares`, body.includes(String(b.plan.shares)), 'shares');
    const chart = card.locator('.ss-trade__chart-mount .sc-chart, .ss-trade__chart-mount svg');
    check(`${variant} ${b.ticker} chart drawn`, (await chart.count()) >= 1, 'no chart');
    check(`${variant} ${b.ticker} chart aria`, (await card.locator('[aria-label]').first().getAttribute('aria-label') || '').length > 20, 'aria');
    const beyond = data.beyond_cap.includes(b.ticker);
    const order = await card.locator('pre[data-order]').count();
    eq(`${variant} ${b.ticker} order block ${beyond ? 'withheld' : 'shown'}`, order, beyond ? 0 : 1);
    if (!beyond) {
      const pre = await card.locator('pre[data-order]').innerText();
      const o = b.plan.order_json;
      check(`${variant} ${b.ticker} ticket line 1`, pre.startsWith(`BUY ${o.quantity} ${o.symbol}`), pre);
      check(`${variant} ${b.ticker} ticket stop and limit`, pre.includes('stop ' + usd(o.stop_price)) && pre.includes('limit ' + usd(o.limit_price)), pre);
      check(`${variant} ${b.ticker} ticket OTO leg`, pre.includes('then OTO → SELL ' + o.then.quantity) && pre.includes(usd(o.then.stop_price)), pre);
      check(`${variant} ${b.ticker} read-back`, body.includes(b.plan.order_line), 'order_line');
      check(`${variant} ${b.ticker} ticket quantity is the plan's shares`, o.quantity === b.plan.shares && o.then.quantity === b.plan.shares, `${o.quantity} vs ${b.plan.shares}`);
      check(`${variant} ${b.ticker} sized at the limit`, body.includes('sized at\n' + usd(b.plan.sizing_price)) || body.includes('sized at ' + usd(b.plan.sizing_price)), 'sizing_price');
      check(`${variant} ${b.ticker} risk and cap hold at the limit`, b.plan.shares * (o.limit_price - b.plan.stop) <= b.plan.sizing.budget_usd + 1e-9 && b.plan.shares * o.limit_price <= b.plan.sizing.cap_usd + 1e-9, 'inequalities');
      for (const term of b.plan.order_terms || []) check(`${variant} ${b.ticker} order term printed`, body.includes(term), term.slice(0, 40));
      check(`${variant} ${b.ticker} no plain-limit fallback`, !/If your app has no stop-limit/.test(body), 'fallback');
      // the copy button hands the clipboard the ticket as printed
      await card.locator('button[data-copy]').first().click();
      const copied = await page.evaluate(() => navigator.clipboard.readText()).catch(() => null);
      if (copied !== null) eq(`${variant} ${b.ticker} copied text is the ticket`, copied, pre);
      else console.log(`  (clipboard not readable for ${b.ticker}; the copy check was skipped)`);
    } else {
      const cut = data.cash_budget.cut.find((c) => c.ticker === b.ticker) || {};
      const words = CUT_WORDS[cut.kind] || 'beyond the slot cap';
      check(`${variant} ${b.ticker} says why there is no ticket (${cut.kind})`, body.includes(words), body.slice(0, 300));
      if (cut.reason) check(`${variant} ${b.ticker} no-ticket reason printed`, body.includes(cut.reason), cut.reason.slice(0, 60));
      if (cut.kind === 'withheld') check(`${variant} ${b.ticker} withheld card keeps the setup`, body.includes(usd(b.plan.stop)) && body.includes(String(b.plan.shares)), 'setup');
    }
    eq(`${variant} ${b.ticker} exit timeline rows`, await card.locator('.sc-timeline__item').count(), b.plan.exit_schedule.length);
    if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} claude read`, body.includes(b.claude.reason), 'reason');
    else check(`${variant} ${b.ticker} says the model did not answer`, body.includes('the model did not answer'), 'nomodel');
    const q = b.quality, miss = q.checks.find((c) => !c.pass);
    check(`${variant} ${b.ticker} foot counts the checks`, body.includes(`of ${q.checks.length} checks pass (${q.passes} of the ${q.of} letters)`), 'foot');
    if (miss) check(`${variant} ${b.ticker} foot names the miss`, body.includes(miss.label), miss.label);
  }
  const lede = await text(page, '#tomorrow-lede');
  if (!trades.length) check(`${variant} lede explains no trades`, /No burst reached|red|closed/.test(lede), lede);

  // the open model plans
  const WALKED = ['hold', 'sell_half', 'sell_into_strength', 'exit', 'stopped', 'expired'];
  eq(`${variant} open plan rows`, await count(page, '#hold-rows article.ss-plan'), data.open_plans.length);
  check(`${variant} the rail is labelled as model plans, not holdings`, (await text(page, '#hold')).includes('Open model plans') && !(await text(page, '#hold')).includes('What you hold'), 'label');
  for (const p of data.open_plans) {
    const row = page.locator(`#hold-rows article.ss-plan[data-ticker="${p.ticker}"]`);
    const body = await row.innerText();
    check(`${variant} ${p.ticker} instruction verbatim`, body.includes(p.instruction), body.slice(0, 200));
    check(`${variant} ${p.ticker} day and shares`, body.includes(`day ${p.day} of 5`) && body.includes(`${p.shares} sh`), body.slice(0, 120));
    eq(`${variant} ${p.ticker} status attr`, await row.getAttribute('data-status'), p.status);
    const drawn = WALKED.includes(p.status) && p.last_close !== null && p.targets;
    eq(`${variant} ${p.ticker} benchmark ${drawn ? 'drawn' : 'not drawn'}`, await row.locator('.sc-benchmark').count(), drawn ? 1 : 0);
    if (p.status === 'uncertain') check(`${variant} ${p.ticker} uncertain row says the model holds nothing`, body.includes('UNCERTAIN') && body.includes('the model holds no position here'), body.slice(-200));
    if (typeof p.sold === 'number' && p.sold > 0 && p.remaining > 0) check(`${variant} ${p.ticker} whole-share sale in the instruction`, body.includes(`${p.sold} of ${p.shares}`) && body.includes(`remaining ${p.remaining}`), p.instruction);
  }
  if (!data.open_plans.length) check(`${variant} says no open plans`, (await text(page, '#hold-rows')).includes('No open model plans'), 'hold');

  // the budget and the order sheet
  const budget = await text(page, '#budget');
  check(`${variant} budget prints the record's own allocation sentence`, budget.includes(data.cash_budget.sentence) && budget.includes(`${data.cash_budget.slots_used} of ${data.cash_budget.slots_max} slots`), budget);
  check(`${variant} budget is labelled model allocation`, budget.includes('Model allocation') && budget.includes('not a balance'), budget);
  for (const c of data.cash_budget.cut) check(`${variant} cut ${c.ticker} explained`, budget.includes('No ticket: ' + c.ticker) && budget.includes(c.reason), budget);
  const withOrders = trades.filter((b) => b.plan && b.plan.order_json);
  eq(`${variant} order sheet rows`, await count(page, '#order-sheet tbody tr[data-ticker]'), withOrders.length);
  if (!withOrders.length) check(`${variant} order sheet says no orders`, (await text(page, '#order-sheet')).includes('No orders'), 'sheet');
  else {
    const foot = await text(page, '#order-sheet tfoot');
    const committed = withOrders.reduce((a, b) => a + b.plan.position_usd, 0), risk = withOrders.reduce((a, b) => a + b.plan.risk_usd, 0);
    check(`${variant} sheet foot totals`, foot.includes(usd(committed, 0)) && foot.includes(usd(risk, 0)), foot);
  }

  // alerts
  eq(`${variant} alert rows`, await count(page, '#alerts-table tbody tr'), data.watchlist.top.length);
  eq(`${variant} alerts lede`, await text(page, '#alerts-lede'), data.watchlist.instruction);
  for (const r of data.watchlist.top) {
    const row = await page.locator(`#alerts-table tr[data-ticker="${r.ticker}"]`).innerText();
    check(`${variant} alert ${r.ticker} trigger and stop`, row.includes(usd(r.plan.trigger)) && row.includes(usd(r.plan.stop)), row);
    check(`${variant} alert ${r.ticker} ticket`, r.plan.order_line ? row.includes(r.plan.order_line) : row.includes('no order'), 'order_line');
    check(`${variant} alert ${r.ticker} box`, row.includes(`${r.box.sessions} sessions`), row);
  }
  if (data.watchlist.also_quiet.length) eq(`${variant} also-quiet rows`, await count(page, '#also-quiet tbody tr'), data.watchlist.also_quiet.length);

  // the scan matrix, opened the way a reader opens it
  if (data.bursts.length) {
    await page.evaluate(() => { const d = document.getElementById('scan-details'); if (d) d.open = true; });
    eq(`${variant} matrix rows`, await count(page, '#scan-table tbody tr'), data.bursts.length);
    const first = data.bursts[0];
    eq(`${variant} matrix columns`, await count(page, '#scan-table thead th'), first.quality.checks.length + 2);
    for (const b of data.bursts) {
      const row = page.locator(`#burst-${b.ticker}`);
      const cells = await row.locator('td .sc-signal__label').allInnerTexts();
      const want = b.quality.checks.map((c) => (b.quality.vetoes.includes('up_days') && c.key === 'two_days') || (b.quality.vetoes.includes('not_linear') && c.key === 'linearity') ? 'veto' : c.pass ? (c.marginal ? 'partial' : 'pass') : (c.status === 'unmeasured' ? 'not measured' : c.marginal ? 'partial' : 'fail'));
      eq(`${variant} ${b.ticker} matrix verdicts`, cells.map((t) => t.split(' · ')[0]), want);
      const grade = await row.locator('.sc-signal-matrix__value').innerText();
      check(`${variant} ${b.ticker} matrix grade`, grade.includes(b.grade), grade);
      if (data.trades.includes(b.ticker)) check(`${variant} ${b.ticker} row links to its card`, (await row.locator(`a[href="#trade-${b.ticker}"]`).count()) === 1, 'link');
    }
    const sorted = await page.locator('#scan-table tbody tr').evaluateAll((rows) => rows.map((r) => +r.dataset.score));
    check(`${variant} matrix sorted by score`, sorted.every((s, i) => i === 0 || sorted[i - 1] >= s), sorted.join(','));
  } else {
    check(`${variant} scan says nothing found`, (await text(page, '#scan-body')).includes('The scan found no burst'), 'scan');
  }
  if (data.closest_miss && data.closest_miss.sentence && !trades.length) check(`${variant} closest miss`, (await text(page, '#closest-miss')).includes(data.closest_miss.sentence), 'miss');
  else eq(`${variant} no closest miss box`, await count(page, '#closest-miss'), 0);

  // the record
  const record = await text(page, '#record-card');
  const sc = data.scorecard;
  check(`${variant} scorecard plans`, record.includes(`plans\n${sc.plans}`) || record.includes(`plans ${sc.plans}`), record.slice(0, 200));
  check(`${variant} scorecard readable chip`, record.includes(sc.readable ? 'readable' : 'not yet readable'), 'chip');
  check(`${variant} scorecard settled count`, record.includes(`${sc.settled} settled`), record.slice(0, 300));
  check(`${variant} scorecard uncertain count`, record.includes(`${sc.uncertain} uncertain`), record.slice(0, 300));
  if (sc.uncertain) for (const r of sc.uncertain_reasons) check(`${variant} scorecard uncertain reason ${r.kind}`, record.includes(`${r.count} ${r.words}`), r.kind);
  if (sc.readable) check(`${variant} scorecard win rate`, record.includes((100 * sc.win_rate).toFixed(0) + '%'), record);
  else check(`${variant} scorecard prints no rate`, !/win rate\n\d+%/.test(record), record);
  eq(`${variant} fourteen nights`, await count(page, '#nights .ss-night'), 14);
  const known = Object.fromEntries(data.nights.map((n) => [n.session, n.status]));
  const dots = await page.locator('#nights .ss-night').evaluateAll((els) => els.map((e) => [e.dataset.session, e.dataset.status]));
  for (const [session, status] of dots) eq(`${variant} night ${session}`, status, known[session] || 'missing');

  // next
  const next = await text(page, '#next-h3');
  if (variant === 'closed') check(`${variant} next: plans unchanged`, next.startsWith('Plans unchanged'), next);
  else if (data.breadth.regime.verdict === 'red') check(`${variant} next: no new longs`, next.startsWith('No new longs'), next);
  else if (withOrders.length) check(`${variant} next: place N orders`, next.startsWith(`Place the ${withOrders.length} order`), next);
  else check(`${variant} next: nothing new`, /^Nothing/.test(next), next);

  // footer and errors
  check(`${variant} footer names the feed and the rules`, (await text(page, '#foot-line')).includes(data.app.rules_version), 'foot');
  eq(`${variant} page errors`, errors, []);
  if (aborted.length) console.log(`  (${aborted.length} chart/font requests not served, as expected offline)`);
  if (shotsDir) {
    await mkdir(shotsDir, { recursive: true });
    await page.screenshot({ path: path.join(shotsDir, `${variant}-1280-dark.png`), fullPage: true });
    if (variant === 'full') {
      for (const [sel, name] of [['#cover', 'cover'], ['#run-strip', 'strip'], ['#breadth', 'breadth'], ['#trades article.ss-trade', 'trade-card'], ['#hold', 'hold'], ['#orders', 'orders'], ['#alerts', 'alerts'], ['#scan', 'scan'], ['#record', 'record'], ['#next', 'next']]) {
        try { await page.locator(sel).first().screenshot({ path: path.join(shotsDir, `full-${name}-1280.png`) }); } catch (e) { console.log(`  (no element shot for ${sel}: ${e.message.split('\n')[0]})`); }
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(150);
    await page.screenshot({ path: path.join(shotsDir, `${variant}-390-dark.png`), fullPage: true });
  }
  await context.close();
  if (shotsDir && variant === 'full') {
    const light = await open(browser, base, `/tests/fixtures/page/${variant}.json`, FRESH_NOW, 1280, 'light');
    await light.page.screenshot({ path: path.join(shotsDir, `${variant}-1280-light.png`), fullPage: true });
    eq(`${variant} light page errors`, light.errors, []);
    await light.context.close();
  }
}

const SENTENCES = {
  universe_cached: 'The stock directory could not ',
  coverage_thin: 'Part of the universe was not r',
  claude_unavailable: 'The model did not answer; ever',
  claude_partial: 'The model answered for some na',
  chart_missing: 'A chart did not render; the gr',
  email_failed: 'The digest could not be delive',
  push_retried: 'Committing the record took mor'
};

async function checkStates(browser, base, data) {
  console.log('-- states the clock decides');
  for (const [name, now, chipRe, state] of [
    ['pending', PENDING_NOW, /pending/, 'pending'],
    ['pending-after-retry', '2026-09-12T00:30:00Z', /pending/, 'pending'],   // Friday 8:30 PM ET: the retry has just fired
    ['stale1', STALE1_NOW, /STALE · 1 session behind/, 'stale1'],
    ['stale2', STALE2_NOW, /STALE · \d+ sessions behind/, 'stale2']]) {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', now, 1280);
    const chip = await text(page, '#status-slot .sc-chip');
    check(`${name} chip`, chipRe.test(chip), chip);
    eq(`${name} state`, await page.getAttribute('html', 'data-ss-rendered'), state);
    check(`${name} next says do not place`, (await text(page, '#next-h3')).startsWith('Do not place these orders'), 'next');
    eq(`${name} cover action falls back to the model plans`, await text(page, '#cover-action'), 'Open model plans');
    if (state !== 'pending') check(`${name} status line links the run log`, (await page.locator('#status-line a[href*="actions/workflows/evening.yml"]').count()) === 1, 'link');
    eq(`${name} page errors`, errors, []);
    if (shotsDir && name === 'stale2') await page.screenshot({ path: path.join(shotsDir, 'stale2-1280-dark.png'), fullPage: true });
    await context.close();
  }
  // a fresh record whose run failed before publishing: the record says so
  const failed = JSON.parse(JSON.stringify(data));
  failed.run.status = 'failed';
  const failedPath = '/tests/fixtures/page/.failed.json';
  await mkdir(path.dirname(path.join(ROOT, failedPath)), { recursive: true });
  const { writeFile, unlink } = await import('node:fs/promises');
  await writeFile(path.join(ROOT, failedPath), JSON.stringify(failed));
  try {
    const { context, page, errors } = await open(browser, base, failedPath, FRESH_NOW, 1280);
    eq('failed chip', await text(page, '#status-slot .sc-chip'), 'no verdict');
    eq('failed state', await page.getAttribute('html', 'data-ss-rendered'), 'failed');
    eq('failed page errors', errors, []);
    await context.close();
  } finally { await unlink(path.join(ROOT, failedPath)); }
  // a record missing a cosmetic field still renders, with no undefined or NaN in sight
  console.log('-- a field missing');
  const drop = (obj, path) => { const parts = path.split('.'); let o = obj; for (const p of parts.slice(0, -1)) o = Array.isArray(o) ? o[0] : o[p]; const last = parts[parts.length - 1]; if (Array.isArray(o)) delete o[0][last]; else delete o[last]; };
  for (const field of ['bursts.quality.checks.threshold', 'bursts.quality.checks.label', 'breadth.up4', 'open_plans.entry_ref', 'open_plans.targets', 'run.reads', 'bursts.claude', 'watchlist.top.plan']) {
    const copy = JSON.parse(JSON.stringify(data));
    const parts = field.split('.'); let o = copy;
    for (let i = 0; i < parts.length - 1; i++) { o = o[parts[i]]; if (Array.isArray(o)) o = o[0]; }
    delete o[parts[parts.length - 1]];
    const dropPath = `/tests/fixtures/page/.dropped.json`;
    await writeFile(path.join(ROOT, dropPath), JSON.stringify(copy));
    try {
      const { context, page, errors } = await open(browser, base, dropPath, FRESH_NOW, 1280);
      const state = await page.getAttribute('html', 'data-ss-rendered');
      check(`without ${field} the page still renders`, state && state !== 'error', state);
      const body = await page.locator('body').innerText();
      check(`without ${field} nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      eq(`without ${field} page errors`, errors, []);
      await context.close();
    } finally { await unlink(path.join(ROOT, dropPath)); }
  }
  // no record at all
  const { context, page } = await open(browser, base, '/tests/fixtures/page/does-not-exist.json', FRESH_NOW, 1280);
  eq('missing record h1', await text(page, '#cover-h1'), 'The record could not be read.');
  eq('missing record state', await page.getAttribute('html', 'data-ss-rendered'), 'error');
  check('missing record next', (await text(page, '#next-h3')).startsWith('Do not place any order'), 'next');
  await context.close();
}

// playwright is not a repo dependency: a global install beside node (the
// way this sandbox has it) or NODE_PATH works too, the way chart_check.mjs loads it.
async function loadChromium() {
  const tries = [
    () => import('playwright'),
    ...[...(process.env.NODE_PATH || '').split(':'), path.resolve(path.dirname(process.execPath), '..', 'lib', 'node_modules')]
      .filter(Boolean)
      .map((root) => () => import(pathToFileURL(path.join(root, 'playwright', 'index.js')).href))
  ];
  for (const t of tries) { try { const m = await t(); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; } catch { /* next */ } }
  return null;
}

async function main() {
  const chromium = await loadChromium();
  if (!chromium) { console.log('playwright is not installed: npm install --no-save playwright'); process.exit(1); }
  for (const v of VARIANTS) if (!existsSync(path.join(FIXTURES, `${v}.json`))) { console.log(`missing fixture ${v}.json -- run python tools/make_fixture.py`); process.exit(1); }
  const { server, base } = await serve();
  const browser = await chromium.launch();
  try {
    let full = null;
    for (const v of VARIANTS) {
      const data = JSON.parse(await readFile(path.join(FIXTURES, `${v}.json`), 'utf8'));
      if (v === 'full') full = data;
      await checkVariant(browser, base, v, data);
    }
    await checkStates(browser, base, full);
  } finally {
    await browser.close();
    server.close();
  }
  console.log(`\n${checks - failures}/${checks} page checks passed${shotsDir ? '; screenshots in ' + shotsDir : ''}`);
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
