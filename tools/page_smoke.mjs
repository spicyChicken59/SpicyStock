#!/usr/bin/env node
/* Open docs/index.html against every fixture the pipeline generated and read
   the page back through a real browser: the status chip, the market bar,
   the two stages and their stocks, the chosen stock's chart, decision
   summary, conditions, plan and ticket, the open model plans, the
   scorecard, the tickets and the scan disclosures, the next-action box --
   each compared with the record the page was handed, never with the page's
   own source. Then the navigation itself: search, the chooser, the
   keyboard, deep links, Back, the old anchors, unknown routes and symbols,
   rapid switching; and the states no fixture can carry: a record viewed
   days later (stale), a field missing, a chart missing, no record at all.

     node tools/page_smoke.mjs                # every check, no screenshots
     node tools/page_smoke.mjs --shots DIR    # also PNGs at 1280 and 390 px, dark and light

   Exit 1 on any failed check or any page error (a console error, an uncaught
   exception, a failed request that is not a chart PNG or a Google font).
   Needs playwright (npm install --no-save playwright) and its chromium. */
import { createServer } from 'node:http';
import { readFile, stat, mkdir, writeFile, unlink } from 'node:fs/promises';
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
const TRADE_GRADES = ['A+', 'A'];   // the grades the run gives an order (pipeline.TRADE_GRADES; the record archives them under rules.pipeline)

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

// why an A-quality plan has no ticket, as the budget's cut kinds spell it (src/plan.py CUT_KINDS)
const CUT_WORDS = { withheld: 'ticket withheld', slot_cap: 'beyond the slot cap', equity: 'beyond the configured equity', no_shares: 'no whole share', no_new_longs: 'no new longs' };

async function open(browser, base, dataUrl, now, width, opts) {
  opts = opts || {};
  const context = await browser.newContext({ viewport: { width, height: opts.height || 900 }, colorScheme: opts.theme || 'dark', reducedMotion: opts.reducedMotion || 'no-preference', permissions: ['clipboard-read', 'clipboard-write'] });
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
  }, { dataUrl, now, theme: opts.theme });
  await page.goto(base + '/docs/index.html' + (opts.hash || ''), { waitUntil: 'load' });
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
const hash = (page) => page.evaluate(() => location.hash);
const go = async (page, h) => { await page.evaluate((h) => { location.hash = h; }, h); await page.waitForTimeout(120); };
const visibleView = (page) => page.evaluate(() => Array.from(document.querySelectorAll('.ss-view')).filter((s) => !s.hidden).map((s) => s.id));
const openAll = (page, sel) => page.evaluate((sel) => document.querySelectorAll(sel).forEach((d) => { d.open = true; }), sel);
const active = (page) => page.evaluate(() => { const a = document.activeElement; return a ? (a.id || '') + '/' + (a.className || '') + '/' + (a.dataset ? a.dataset.ticker || '' : '') : ''; });
const clickPick = async (page, ticker) => { await page.locator(`#pick-list .ss-pick[data-ticker="${ticker}"]`).click(); await page.waitForTimeout(150); };

// what the record says each stock's status is (the page reads the same fields; the smoke reads them again, on its own)
function burstStatus(b, data) {
  const cut = (data.cash_budget.cut || []).find((c) => c.ticker === b.ticker);
  if (data.trades.includes(b.ticker) && b.plan && b.plan.order_json) return 'ticket';
  if (cut) return cut.kind;
  if (b.plan && b.plan.eligible === false) return 'withheld';
  if (b.plan && b.plan.action === 'no_new_longs') return 'no_new_longs';
  if ((b.quality.vetoes || []).length) return 'vetoed';
  if (!TRADE_GRADES.includes(b.grade)) return 'below_grade';
  if (data.breadth.regime.verdict === 'red') return 'no_new_longs';
  return b.plan ? 'no_order' : 'no_plan';
}
function coilStatus(r) {
  const p = r.plan;
  if (!p) return 'watch';
  if (p.eligible === false) return 'withheld';
  if (p.action === 'no_new_longs') return 'no_new_longs';
  if (p.order_json) return 'ticket';
  return p.shares === 0 ? 'no_shares' : 'no_order';
}

async function checkDetail(page, variant, b, data, blocked) {
  const stage = data.trades ? 'bursts' : 'bursts';
  await openAll(page, '#detail details');
  const body = await text(page, '#detail');
  const head = await text(page, '#detail .ss-detail__head');
  const status = burstStatus(b, data);
  eq(`${variant} ${b.ticker} detail names the stock`, await text(page, '#detail-h2'), b.ticker);
  eq(`${variant} ${b.ticker} route`, await hash(page), `#/explore/${stage}/${b.ticker}`);
  check(`${variant} ${b.ticker} grade chip`, head.includes(b.grade + ' · ' + b.score.toFixed(1)), head.slice(0, 200));
  check(`${variant} ${b.ticker} nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
  // the chart: the archived bars, or the designed absence
  if ((b.series || []).length) {
    const chart = page.locator('#detail .sc-chart--stock');
    eq(`${variant} ${b.ticker} chart drawn`, await chart.count(), 1);
    eq(`${variant} ${b.ticker} chart is this stock's`, await chart.getAttribute('data-ticker'), b.ticker);
    check(`${variant} ${b.ticker} chart aria`, ((await chart.getAttribute('aria-label')) || '').length > 20, 'aria');
    eq(`${variant} ${b.ticker} chart shows 60 sessions first`, await chart.getAttribute('data-sessions'), String(Math.min(60, b.series.length)));
    check(`${variant} ${b.ticker} burst legend`, (await text(page, '#detail .sc-legend')).includes('burst'), 'legend');
  } else {
    eq(`${variant} ${b.ticker} chart unavailable state`, await count(page, '#detail [data-chart="unavailable"]'), 1);
    eq(`${variant} ${b.ticker} no chart drawn`, await count(page, '#detail .sc-chart--stock'), 0);
  }
  // the decision summary: four answers from the record's own sentences
  eq(`${variant} ${b.ticker} four decision items`, await count(page, '#detail .ss-decision__item'), 4);
  const why = await text(page, '#detail .ss-decision__item[data-item="why"]');
  const summary = (b.summary || '').replace(/^[A-Z0-9.\-]+:\s*/, '').split(/(?<=[.!?])\s/)[0];
  check(`${variant} ${b.ticker} why: the summary`, why.includes(summary), summary);
  const q = b.quality, miss = q.checks.find((c) => !c.pass);
  check(`${variant} ${b.ticker} why: counts the checks`, why.includes(`of ${q.checks.length} checks pass (${q.passes} of the ${q.of} letters)`), why);
  if (miss) check(`${variant} ${b.ticker} why: names the miss`, why.includes(miss.label), miss.label);
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} why: the chart reader`, why.includes(b.claude.reason), 'reason');
  const need = await text(page, '#detail .ss-decision__item[data-item="need"]');
  const entry = b.plan ? (b.plan.exit_schedule || []).find((s) => s.key === 'entry' || s.day === 1) : null;
  if (entry) check(`${variant} ${b.ticker} need: the day-1 instruction`, need.toLowerCase().includes(entry.instruction.slice(1, 60).toLowerCase()), need);
  if (status !== 'ticket') check(`${variant} ${b.ticker} need: says no ticket`, /No ticket tonight|Nothing:/.test(need), need);
  const wait = await text(page, '#detail .ss-decision__item[data-item="wait"]');
  if (b.plan && b.plan.pre_open_check) check(`${variant} ${b.ticker} wait: the pre-open check`, wait.toLowerCase().includes(b.plan.pre_open_check.slice(1, 60).toLowerCase()), wait);
  if (b.plan) check(`${variant} ${b.ticker} wait: the stop`, wait.includes(usd(b.plan.stop)), wait);
  const risk = await text(page, '#detail .ss-decision__item[data-item="risk"]');
  if (b.claude && b.claude.key_risk) check(`${variant} ${b.ticker} risk: the key risk`, risk.includes(b.claude.key_risk.replace(/\.$/, '')), risk);
  if (!(b.series || []).length) check(`${variant} ${b.ticker} risk: names the missing bars`, risk.includes('No bars are archived'), risk);
  // the action area: a ticket, or the reason there is none; never "buy now"
  const action = await text(page, '#detail .ss-action');
  const ticketAttr = await page.locator('#detail .ss-action').getAttribute('data-ticket');
  check(`${variant} ${b.ticker} action never says buy now`, !/buy now/i.test(action), action);
  const btn = await text(page, '#detail .ss-action button');
  if (status === 'ticket' && !blocked) {
    eq(`${variant} ${b.ticker} action carries the order`, ticketAttr, 'order');
    check(`${variant} ${b.ticker} action prints the order line`, action.includes(b.plan.order_line), action);
    eq(`${variant} ${b.ticker} action button`, btn, 'View conditional plan');
  } else if (status === 'ticket') {
    eq(`${variant} ${b.ticker} action withholds the order on a blocked page`, ticketAttr, 'blocked');
    eq(`${variant} ${b.ticker} action button`, btn, 'Inspect conditions');
  } else {
    eq(`${variant} ${b.ticker} action status`, ticketAttr, status);
    eq(`${variant} ${b.ticker} action button`, btn, 'Inspect conditions');
    const cut = (data.cash_budget.cut || []).find((c) => c.ticker === b.ticker);
    if (cut) {
      check(`${variant} ${b.ticker} says why there is no ticket (${cut.kind})`, action.includes(CUT_WORDS[cut.kind]), action.slice(0, 200));
      check(`${variant} ${b.ticker} no-ticket reason printed`, action.toLowerCase().includes(cut.reason.slice(0, 60).toLowerCase()), cut.reason.slice(0, 60));
    } else if (status === 'below_grade') check(`${variant} ${b.ticker} says the grade is under the line`, action.includes('graded ' + b.grade) || action.includes('Graded ' + b.grade), action);
    else if (status === 'no_new_longs') check(`${variant} ${b.ticker} says no new longs`, /no new longs/i.test(action), action);
  }
  // the conditions: one tile per criterion, the verdict in words
  const tiles = await page.locator('#disc-checklist .ss-checks .sc-signal').evaluateAll((els) => els.map((e) => [e.dataset.check, e.dataset.verdict]));
  eq(`${variant} ${b.ticker} one tile per check`, tiles.map((t) => t[0]), q.checks.map((c) => c.key));
  const want = q.checks.map((c) => (q.vetoes.includes('up_days') && c.key === 'two_days') || (q.vetoes.includes('not_linear') && c.key === 'linearity') ? 'veto' : c.pass ? (c.marginal ? 'partial' : 'pass') : (c.status === 'unmeasured' ? 'not measured' : 'fail'));
  eq(`${variant} ${b.ticker} tile verdicts`, tiles.map((t) => t[1]), want);
  const conditions = await text(page, '#disc-checklist');
  check(`${variant} ${b.ticker} conditions carry the gain and the volume`, conditions.includes(`+${b.gain_pct.toFixed(1)}%`) && conditions.includes(b.volume_vs_prior.toFixed(1) + '× volume'), conditions.slice(0, 200));
  if (q.base && q.base.sessions) check(`${variant} ${b.ticker} conditions carry the base`, conditions.includes(`${q.base.sessions} sessions`), 'base');
  // the plan and the order
  const planText = await text(page, '#disc-plan');
  const order = await count(page, '#detail pre[data-order]');
  if (b.plan) {
    check(`${variant} ${b.ticker} buy zone`, planText.includes(usd(b.plan.entry_low) + ' – ' + usd(b.plan.entry_high)), 'zone');
    check(`${variant} ${b.ticker} stop`, planText.includes(usd(b.plan.stop)), 'stop');
    check(`${variant} ${b.ticker} shares`, planText.includes(String(b.plan.shares)), 'shares');
    check(`${variant} ${b.ticker} sized at the limit`, planText.includes('sized at\n' + usd(b.plan.sizing_price)) || planText.includes('sized at ' + usd(b.plan.sizing_price)), 'sizing_price');
    check(`${variant} ${b.ticker} no plain-limit fallback`, !/If your app has no stop-limit/.test(body), 'fallback');
    eq(`${variant} ${b.ticker} exit timeline rows`, await count(page, '#disc-exits .sc-timeline__item'), b.plan.exit_schedule.length);
  } else {
    check(`${variant} ${b.ticker} says there is no plan`, planText.includes('No plan'), planText);
    check(`${variant} ${b.ticker} says there are no model exits`, (await text(page, '#disc-exits')).includes('no model exits'), 'exits');
  }
  eq(`${variant} ${b.ticker} order block ${status === 'ticket' && !blocked ? 'shown' : 'withheld'}`, order, status === 'ticket' && !blocked ? 1 : 0);
  if (status === 'ticket' && !blocked) {
    const pre = await page.locator('#detail pre[data-order]').innerText();
    const o = b.plan.order_json;
    check(`${variant} ${b.ticker} ticket line 1`, pre.startsWith(`BUY ${o.quantity} ${o.symbol}`), pre);
    check(`${variant} ${b.ticker} ticket stop and limit`, pre.includes('stop ' + usd(o.stop_price)) && pre.includes('limit ' + usd(o.limit_price)), pre);
    check(`${variant} ${b.ticker} ticket OTO leg`, pre.includes('then OTO → SELL ' + o.then.quantity) && pre.includes(usd(o.then.stop_price)), pre);
    check(`${variant} ${b.ticker} read-back`, planText.includes(b.plan.order_line), 'order_line');
    check(`${variant} ${b.ticker} ticket quantity is the plan's shares`, o.quantity === b.plan.shares && o.then.quantity === b.plan.shares, `${o.quantity} vs ${b.plan.shares}`);
    check(`${variant} ${b.ticker} risk and cap hold at the limit`, b.plan.shares * (o.limit_price - b.plan.stop) <= b.plan.sizing.budget_usd + 1e-9 && b.plan.shares * o.limit_price <= b.plan.sizing.cap_usd + 1e-9, 'inequalities');
    for (const term of b.plan.order_terms || []) check(`${variant} ${b.ticker} order term printed`, planText.includes(term), term.slice(0, 40));
    // the copy button hands the clipboard the ticket as printed
    await page.locator('#detail button[data-copy]').first().click();
    const copied = await page.evaluate(() => navigator.clipboard.readText()).catch(() => null);
    if (copied !== null) eq(`${variant} ${b.ticker} copied text is the ticket`, copied, pre);
    else console.log(`  (clipboard not readable for ${b.ticker}; the copy check was skipped)`);
  } else if (status === 'withheld' && b.plan) check(`${variant} ${b.ticker} withheld keeps the setup`, planText.includes(usd(b.plan.stop)) && planText.includes(String(b.plan.shares)), 'setup');
  if (status !== 'ticket' || blocked) check(`${variant} ${b.ticker} plan says why there is no order`, /No ticket tonight|No order is offered|No plan/.test(planText), planText.slice(-200));
  // provenance
  const prov = await text(page, '#disc-provenance');
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} claude read`, prov.includes(b.claude.reason), 'reason');
  else check(`${variant} ${b.ticker} says the model did not answer`, prov.includes('the model did not answer'), 'nomodel');
  check(`${variant} ${b.ticker} provenance names the rules`, prov.includes(data.app.rules_version), 'rules');
}

async function checkCoil(page, variant, r, data, blocked, quiet) {
  await openAll(page, '#detail details');
  const body = await text(page, '#detail');
  const status = quiet ? 'watch' : coilStatus(r);
  eq(`${variant} ${r.ticker} detail names the stock`, await text(page, '#detail-h2'), r.ticker);
  eq(`${variant} ${r.ticker} route`, await hash(page), `#/explore/setting-up/${r.ticker}`);
  check(`${variant} ${r.ticker} nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
  if ((r.series || []).length) {
    const chart = page.locator('#detail .sc-chart--stock');
    eq(`${variant} ${r.ticker} chart drawn`, await chart.count(), 1);
    eq(`${variant} ${r.ticker} chart is an anticipation chart`, await chart.getAttribute('data-stage'), 'setting-up');
    check(`${variant} ${r.ticker} no burst candle on a coil`, !(await text(page, '#detail .sc-legend')).includes('burst') && (await count(page, '#detail .sc-chart--stock [data-level="trigger"]')) === (r.plan && r.plan.trigger ? 1 : 0), 'legend/trigger');
  } else eq(`${variant} ${r.ticker} chart unavailable state`, await count(page, '#detail [data-chart="unavailable"]'), 1);
  eq(`${variant} ${r.ticker} four decision items`, await count(page, '#detail .ss-decision__item'), 4);
  const why = await text(page, '#detail .ss-decision__item[data-item="why"]');
  check(`${variant} ${r.ticker} why: the coil's measures`, why.includes(`${r.quiet_days} quiet days`) && why.includes(`${r.range_pct}% range`), why);
  const conditions = await text(page, '#disc-checklist');
  if (r.box) check(`${variant} ${r.ticker} conditions carry the box`, conditions.includes(`${r.box.sessions} sessions`), conditions.slice(0, 200));
  const action = await text(page, '#detail .ss-action'), ticketAttr = await page.locator('#detail .ss-action').getAttribute('data-ticket');
  check(`${variant} ${r.ticker} action never says buy now`, !/buy now/i.test(action), action);
  const planText = await text(page, '#disc-plan');
  if (r.plan) {
    check(`${variant} ${r.ticker} trigger, limit and stop`, planText.includes(usd(r.plan.trigger)) && planText.includes(usd(r.plan.limit)) && planText.includes(usd(r.plan.stop)), planText.slice(0, 300));
    if (r.plan.gap_rule) check(`${variant} ${r.ticker} gap rule printed`, body.toLowerCase().includes(r.plan.gap_rule.slice(0, 40).toLowerCase()), 'gap');
  }
  if (status === 'ticket' && !blocked) {
    eq(`${variant} ${r.ticker} action carries the order`, ticketAttr, 'order');
    check(`${variant} ${r.ticker} action prints the order line`, action.includes(r.plan.order_line), action);
    eq(`${variant} ${r.ticker} order block shown`, await count(page, '#detail pre[data-order]'), 1);
  } else {
    eq(`${variant} ${r.ticker} action status`, ticketAttr, status === 'ticket' ? 'blocked' : status);
    eq(`${variant} ${r.ticker} order block withheld`, await count(page, '#detail pre[data-order]'), 0);
    if (status === 'no_new_longs') check(`${variant} ${r.ticker} says no new longs`, /no new longs|zero tonight/i.test(action), action);
    if (status === 'watch') check(`${variant} ${r.ticker} says it is watched, not ticketed`, /no ticket|no plan/i.test(action), action);
  }
}

async function checkVariant(browser, base, variant, data) {
  console.log(`-- ${variant}`);
  const { context, page, errors, aborted } = await open(browser, base, `/tests/fixtures/page/${variant}.json`, FRESH_NOW, 1280);
  const run = data.run, byTicker = Object.fromEntries(data.bursts.map((b) => [b.ticker, b]));
  const trades = data.trades.map((t) => byTicker[t]);
  const top = data.watchlist.top, also = data.watchlist.also_quiet;
  const settingUp = top.length + also.length;
  const defaultStage = data.bursts.length ? 'bursts' : settingUp ? 'setting-up' : 'bursts';

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

  // the market bar: the verdict, the regime, the session, the record's own call to action
  eq(`${variant} h1`, await text(page, '#cover-h1'), data.cover.h1);
  eq(`${variant} dek`, await text(page, '#cover-dek'), data.cover.dek);
  eq(`${variant} title`, await page.title(), 'SpicyStock · ' + data.cover.h1);
  eq(`${variant} action`, await text(page, '#cover-action'), data.cover.action_label);
  const target = data.cover.action_target;
  check(`${variant} cover action target exists`, (await page.locator(target).count()) === 1, target);
  const facts = await text(page, '#market-facts');
  check(`${variant} market bar names the regime`, facts.includes(data.breadth.regime.verdict.toUpperCase()), facts);
  check(`${variant} market bar names the ratio`, facts.includes(String(data.breadth.ratio_10d)), facts);
  eq(`${variant} explore is the view`, await visibleView(page), ['view-explore']);
  eq(`${variant} nav marks explore`, await page.locator('#nav a[aria-current="page"]').getAttribute('data-view'), 'explore');

  // the stages: two cards with the record's counts; the default stage pressed
  const stages = await page.locator('#stages .ss-stage').evaluateAll((els) => els.map((e) => [e.dataset.stage, +e.dataset.count, e.getAttribute('aria-pressed')]));
  eq(`${variant} stage counts`, stages.map((s) => [s[0], s[1]]), [['bursts', data.bursts.length], ['setting-up', settingUp]]);
  eq(`${variant} default stage pressed`, stages.filter((s) => s[2] === 'true').map((s) => s[0]), [defaultStage]);
  const stageText = await text(page, '#stages');
  const ticketBursts = trades.filter((b) => b.plan && b.plan.order_json).length, ticketCoils = top.filter((r) => coilStatus(r) === 'ticket').length;
  if (data.bursts.length) check(`${variant} bursts card counts the tickets`, stageText.includes(`${ticketBursts} with a ticket`), stageText);
  if (settingUp) check(`${variant} setting-up card counts the tickets`, stageText.includes(`${ticketCoils} with a ticket`), stageText);

  // the stocks of the default stage: one selectable card each, the first chosen, the route canonical
  const pickOf = async () => page.locator('#pick-list .ss-pick').evaluateAll((els) => els.map((e) => [e.dataset.ticker, e.dataset.status, e.getAttribute('aria-pressed')]));
  if (defaultStage === 'bursts' && data.bursts.length) {
    const picks = await pickOf();
    eq(`${variant} one card per burst, in rank order`, picks.map((p) => p[0]), data.bursts.map((b) => b.ticker));
    eq(`${variant} card statuses read off the record`, picks.map((p) => p[1]), data.bursts.map((b) => burstStatus(b, data)));
    eq(`${variant} the first burst is chosen`, picks.filter((p) => p[2] === 'true').map((p) => p[0]), [data.bursts[0].ticker]);
    eq(`${variant} the route names the chosen stock`, await hash(page), `#/explore/bursts/${data.bursts[0].ticker}`);
    for (const b of data.bursts) {
      await clickPick(page, b.ticker);
      const picks2 = await pickOf();
      eq(`${variant} ${b.ticker} chosen in the list`, picks2.filter((p) => p[2] === 'true').map((p) => p[0]), [b.ticker]);
      check(`${variant} ${b.ticker} status line`, (await text(page, '#picks-status')).includes(`${b.ticker} · ${data.bursts.indexOf(b) + 1} of ${data.bursts.length}`), await text(page, '#picks-status'));
      await checkDetail(page, variant, b, data, false);
    }
    // "View conditional plan" opens the plan disclosure and moves focus to it
    const first = trades.find((b) => b.plan && b.plan.order_json);
    if (first) {
      await clickPick(page, first.ticker);
      await page.locator('#detail .ss-action button').click();
      await page.waitForTimeout(150);
      eq(`${variant} the plan disclosure opens on request`, await page.evaluate(() => document.getElementById('disc-plan').open), true);
      check(`${variant} focus lands on the plan`, (await active(page)).startsWith('/'), await active(page));
    }
  } else if (!data.bursts.length) {
    eq(`${variant} the bursts stage says why it is empty`, await count(page, '#pick-list [data-empty="bursts"]'), defaultStage === 'bursts' ? 1 : 0);
    if (defaultStage === 'bursts') {
      check(`${variant} the empty bursts stage explains itself`, /closed|no burst|none/i.test(await text(page, '#pick-list')), await text(page, '#pick-list'));
      eq(`${variant} the detail shows the designed empty state`, await count(page, '#detail [data-detail="empty"]'), 1);
      eq(`${variant} no chart is drawn for nothing`, await count(page, '#detail .sc-chart--stock'), 0);
    }
  }

  // the other stage, chosen deliberately: the coils, or the designed empty state
  await page.locator('#stages .ss-stage[data-stage="setting-up"]').click();
  await page.waitForTimeout(150);
  eq(`${variant} setting-up pressed on request`, await page.locator('#stages .ss-stage[aria-pressed="true"]').getAttribute('data-stage'), 'setting-up');
  check(`${variant} setting-up route`, (await hash(page)).startsWith('#/explore/setting-up'), await hash(page));
  if (settingUp) {
    const picks = await pickOf();
    eq(`${variant} one card per coil`, picks.map((p) => p[0]), top.map((r) => r.ticker).concat(also.map((r) => r.ticker)));
    eq(`${variant} coil statuses read off the record`, picks.map((p) => p[1]), top.map((r) => coilStatus(r)).concat(also.map(() => 'watch')));
    for (const r of top) { await clickPick(page, r.ticker); await checkCoil(page, variant, r, data, false, false); }
    for (const r of also) { await clickPick(page, r.ticker); await checkCoil(page, variant, r, data, false, true); }
  } else {
    eq(`${variant} the empty setting-up stage says so`, await count(page, '#pick-list [data-empty="setting-up"]'), 1);
    eq(`${variant} the empty stage is not switched away from`, await page.locator('#stages .ss-stage[aria-pressed="true"]').getAttribute('data-stage'), 'setting-up');
  }
  // and back: the bursts stage remembers its last chosen stock
  await page.locator('#stages .ss-stage[data-stage="bursts"]').click();
  await page.waitForTimeout(150);
  if (data.bursts.length) {
    const last = trades.find((b) => b.plan && b.plan.order_json) || data.bursts[data.bursts.length - 1];
    eq(`${variant} bursts remembers its stock`, await hash(page), `#/explore/bursts/${last.ticker}`);
    eq(`${variant} remembered stock in the detail`, await text(page, '#detail-h2'), last.ticker);
  }

  // search: a ticker from the other stage switches the stage, visibly; nonsense is a designed empty state
  if (data.bursts.length && settingUp) {
    await page.fill('#search', top.length ? top[0].ticker.toLowerCase() : also[0].ticker.toLowerCase());
    await page.press('#search', 'Enter');
    await page.waitForTimeout(200);
    const t = top.length ? top[0].ticker : also[0].ticker;
    eq(`${variant} search switches the stage`, await hash(page), `#/explore/setting-up/${t}`);
    check(`${variant} search says it switched`, (await text(page, '#picks-status')).includes('switched from Bursts'), await text(page, '#picks-status'));
    eq(`${variant} search clears after a hit`, await page.inputValue('#search'), '');
  }
  if (data.bursts.length || settingUp) {
    await page.fill('#search', 'zzzq');
    await page.waitForTimeout(150);
    eq(`${variant} nonsense search shows the empty-search state`, await count(page, '#pick-list [data-empty="search"]'), 1);
    check(`${variant} empty search names the query`, (await text(page, '#pick-list')).includes('ZZZQ'), await text(page, '#pick-list'));
    eq(`${variant} the chosen stock stays while the list is filtered`, (await count(page, '#detail-h2')), 1);
    await page.locator('#pick-list [data-empty="search"] .sc-btn--ghost').click();
    await page.waitForTimeout(100);
    eq(`${variant} clear search restores the list`, await count(page, '#pick-list [data-empty="search"]'), 0);
  }

  // the keyboard: arrows move between the cards, Enter chooses
  if (data.bursts.length >= 2) {
    await page.locator('#stages .ss-stage[data-stage="bursts"]').click();
    await page.waitForTimeout(100);
    await clickPick(page, data.bursts[0].ticker);
    await page.locator(`#pick-list .ss-pick[data-ticker="${data.bursts[0].ticker}"]`).focus();
    await page.keyboard.press('ArrowDown');
    check(`${variant} ArrowDown moves focus to the next card`, (await active(page)).endsWith('/' + data.bursts[1].ticker), await active(page));
    eq(`${variant} arrow keys do not choose by themselves`, await hash(page), `#/explore/bursts/${data.bursts[0].ticker}`);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    eq(`${variant} Enter chooses the focused card`, await hash(page), `#/explore/bursts/${data.bursts[1].ticker}`);
    eq(`${variant} the detail follows the keyboard`, await text(page, '#detail-h2'), data.bursts[1].ticker);
    await page.keyboard.press('Home');
    check(`${variant} Home moves focus to the first card`, (await active(page)).endsWith('/' + data.bursts[0].ticker), await active(page));
  }

  // rapid switching: every card in a burst of clicks, no waits; the detail ends where the route says
  if (data.bursts.length >= 2) {
    for (const b of data.bursts) await page.locator(`#pick-list .ss-pick[data-ticker="${b.ticker}"]`).click({ noWaitAfter: true });
    await page.waitForTimeout(300);
    const lastB = data.bursts[data.bursts.length - 1];
    eq(`${variant} rapid switching ends on the last click`, await hash(page), `#/explore/bursts/${lastB.ticker}`);
    eq(`${variant} rapid switching: the detail agrees`, await text(page, '#detail-h2'), lastB.ticker);
    eq(`${variant} rapid switching: one chart`, await count(page, '#detail .sc-chart--stock'), (lastB.series || []).length ? 1 : 0);
    check(`${variant} rapid switching: the grade is the record's`, (await text(page, '#detail .ss-detail__head')).includes(lastB.grade + ' · ' + lastB.score.toFixed(1)), 'grade');
  }

  // the tickets disclosure: the model allocation and the order sheet
  await openAll(page, '#orders');
  const withOrders = trades.filter((b) => b.plan && b.plan.order_json);
  check(`${variant} tickets summary counts the orders`, (await text(page, '#orders-summary')).includes(withOrders.length ? `${withOrders.length} order` : 'none'), await text(page, '#orders-summary'));
  const budget = await text(page, '#budget');
  check(`${variant} budget prints the record's own allocation sentence`, budget.includes(data.cash_budget.sentence) && budget.includes(`${data.cash_budget.slots_used} of ${data.cash_budget.slots_max} slots`), budget);
  check(`${variant} budget is labelled model allocation`, budget.includes('Model allocation') && budget.includes('not a balance'), budget);
  for (const c of data.cash_budget.cut) check(`${variant} cut ${c.ticker} explained`, budget.includes('No ticket: ' + c.ticker) && budget.includes(c.reason), budget);
  eq(`${variant} order sheet rows`, await count(page, '#order-sheet tbody tr[data-ticker]'), withOrders.length);
  if (!withOrders.length) check(`${variant} order sheet says no orders`, (await text(page, '#order-sheet')).includes('No orders'), 'sheet');
  else {
    const foot = await text(page, '#order-sheet tfoot');
    const committed = withOrders.reduce((a, b) => a + b.plan.position_usd, 0), risk = withOrders.reduce((a, b) => a + b.plan.risk_usd, 0);
    check(`${variant} sheet foot totals`, foot.includes(usd(committed, 0)) && foot.includes(usd(risk, 0)), foot);
    // a name on the sheet opens its card
    await page.locator(`#order-sheet tr[data-ticker="${withOrders[0].ticker}"] button`).click();
    await page.waitForTimeout(150);
    eq(`${variant} sheet name opens the card`, await text(page, '#detail-h2'), withOrders[0].ticker);
  }

  // the scan disclosure: the matrix, sortable, every name a way into its card
  await openAll(page, '#scan');
  check(`${variant} scan summary counts the bursts`, (await text(page, '#scan-summary')).includes(data.bursts.length ? `${data.bursts.length} burst` : 'no burst'), await text(page, '#scan-summary'));
  if (data.bursts.length) {
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
      eq(`${variant} ${b.ticker} row links to its card`, await row.locator(`button[data-go="#/explore/bursts/${b.ticker}"]`).count(), 1);
    }
    const sorted = await page.locator('#scan-table tbody tr').evaluateAll((rows) => rows.map((r) => +r.dataset.score));
    check(`${variant} matrix sorted by score`, sorted.every((s, i) => i === 0 || sorted[i - 1] >= s), sorted.join(','));
    const lastB = data.bursts[data.bursts.length - 1];
    await page.locator(`#burst-${lastB.ticker} button[data-go]`).click();
    await page.waitForTimeout(150);
    eq(`${variant} matrix name opens the card`, await text(page, '#detail-h2'), lastB.ticker);
    eq(`${variant} matrix name moves focus to the card`, (await active(page)).split('/')[0], 'detail');
  } else {
    check(`${variant} scan says nothing found`, (await text(page, '#scan-body')).includes('The scan found no burst'), 'scan');
  }
  if (data.closest_miss && data.closest_miss.sentence && !trades.length) check(`${variant} closest miss`, (await text(page, '#closest-miss')).includes(data.closest_miss.sentence), 'miss');
  else eq(`${variant} no closest miss box`, await count(page, '#closest-miss'), 0);

  // the record view, then Back: the selection survives the trip
  const before = await hash(page);
  await page.locator('#nav a[data-view="record"]').click();
  await page.waitForTimeout(200);
  eq(`${variant} record view`, await visibleView(page), ['view-record']);
  eq(`${variant} record route`, await hash(page), '#/record');
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
  eq(`${variant} the next action stays on the record view`, await page.locator('#next').isVisible(), true);
  await page.goBack();
  await page.waitForTimeout(250);
  eq(`${variant} Back returns to Explore`, await visibleView(page), ['view-explore']);
  eq(`${variant} Back restores the route`, await hash(page), before);
  if (data.bursts.length) eq(`${variant} Back restores the chosen stock`, await text(page, '#detail-h2'), before.split('/').pop());

  // the market view
  await go(page, '#/market');
  eq(`${variant} market view`, await visibleView(page), ['view-market']);
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

  // the method view: the run strip and the sizing assumptions
  await go(page, '#/method');
  eq(`${variant} method view`, await visibleView(page), ['view-method']);
  const strip = await text(page, '#run-strip');
  check(`${variant} strip carries the graded counts`, strip.includes(`${run.graded.a} A · ${run.graded.a_plus} A+`), strip);
  check(`${variant} strip carries the reads`, strip.includes(`${run.reads.done} of ${run.reads.requested} read`), strip);
  check(`${variant} strip carries the email state`, strip.includes('email ' + run.email), strip);
  const meta = await text(page, '#run-meta');
  check(`${variant} run details name the universe size`, meta.includes(String(run.universe.size).replace(/\B(?=(\d{3})+(?!\d))/g, ',')), meta);
  check(`${variant} run details name Bonde's median night`, strip.includes('239'), strip);
  eq(`${variant} sizing assumptions listed`, await count(page, '#account-notes li'), data.account.notes.length || 1);

  // the old anchors still land: #orders opens the tickets, #hold is the record, #trade-X and #burst-X are the stock
  await go(page, '#orders');
  eq(`${variant} #orders opens the tickets`, await page.evaluate(() => document.getElementById('orders').open && !document.getElementById('view-explore').hidden), true);
  await go(page, '#hold');
  eq(`${variant} #hold is the record view`, await visibleView(page), ['view-record']);
  if (data.bursts.length) {
    const b0 = data.bursts[0];
    await go(page, `#trade-${b0.ticker}`);
    eq(`${variant} #trade-X lands on the stock`, [await visibleView(page), await hash(page), await text(page, '#detail-h2')], [['view-explore'], `#/explore/bursts/${b0.ticker}`, b0.ticker]);
    const bN = data.bursts[data.bursts.length - 1];
    await go(page, `#burst-${bN.ticker}`);
    eq(`${variant} #burst-X lands on the stock`, [await hash(page), await text(page, '#detail-h2')], [`#/explore/bursts/${bN.ticker}`, bN.ticker]);
  }
  if (data.closest_miss && data.closest_miss.sentence && !trades.length) {
    await go(page, '#closest-miss');
    eq(`${variant} #closest-miss opens the scan`, await page.evaluate(() => document.getElementById('scan').open), true);
  }

  // unknown routes and symbols recover, and say so
  await go(page, '#/nowhere');
  eq(`${variant} unknown route shows Explore`, await visibleView(page), ['view-explore']);
  check(`${variant} unknown route is named`, (await text(page, '#picks-status')).includes('There is no #/nowhere'), await text(page, '#picks-status'));
  await go(page, '#/explore/bursts/ZZZQ');
  check(`${variant} unknown symbol is named`, (await text(page, '#picks-status')).includes('No stock ZZZQ'), await text(page, '#picks-status'));
  check(`${variant} unknown symbol keeps the page usable`, (await hash(page)).startsWith('#/explore/bursts'), await hash(page));
  if (top.length) {
    await go(page, `#/explore/bursts/${top[0].ticker}`);
    eq(`${variant} a symbol in the other stage switches to it`, await hash(page), `#/explore/setting-up/${top[0].ticker}`);
    check(`${variant} the switch is announced`, (await text(page, '#picks-status')).includes('shown instead'), await text(page, '#picks-status'));
  }

  // the next action, whatever the view
  await go(page, '#/explore');
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
    await go(page, '#/explore');
    await page.screenshot({ path: path.join(shotsDir, `${variant}-1280-dark.png`), fullPage: true });
    if (variant === 'full') {
      for (const [sel, name] of [['#market-bar', 'market-bar'], ['#stages', 'stages'], ['#workspace', 'workspace'], ['#detail', 'detail'], ['#orders', 'orders'], ['#scan', 'scan'], ['#next', 'next']]) {
        try { await page.locator(sel).first().screenshot({ path: path.join(shotsDir, `full-${name}-1280.png`) }); } catch (e) { console.log(`  (no element shot for ${sel}: ${e.message.split('\n')[0]})`); }
      }
      const withheld = (data.cash_budget.cut || []).find((c) => c.kind === 'withheld');
      if (withheld) { await go(page, `#/explore/bursts/${withheld.ticker}`); await page.locator('#detail').screenshot({ path: path.join(shotsDir, 'full-withheld-1280.png') }); }
      if (top.length) { await go(page, `#/explore/setting-up/${top[0].ticker}`); await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: path.join(shotsDir, 'full-setting-up-1280.png') }); }
      await go(page, '#/record'); await page.screenshot({ path: path.join(shotsDir, 'full-record-1280.png'), fullPage: true });
      await go(page, '#/market'); await page.screenshot({ path: path.join(shotsDir, 'full-market-1280.png'), fullPage: true });
      await go(page, '#/method'); await page.screenshot({ path: path.join(shotsDir, 'full-method-1280.png'), fullPage: true });
      await go(page, '#/explore');
    }
  }
  await context.close();
  if (shotsDir && variant === 'full') {
    const light = await open(browser, base, `/tests/fixtures/page/${variant}.json`, FRESH_NOW, 1280, { theme: 'light' });
    await light.page.screenshot({ path: path.join(shotsDir, `${variant}-1280-light.png`), fullPage: true });
    eq(`${variant} light page errors`, light.errors, []);
    await light.context.close();
  }
}

// the phone: the stage and stock controls in the first screen, a rail of cards, the chooser dialog
async function checkMobile(browser, base, data) {
  console.log('-- the phone');
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844 });
  if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.screenshot({ path: path.join(shotsDir, 'full-390-dark.png') }); await page.screenshot({ path: path.join(shotsDir, 'full-390-dark-full.png'), fullPage: true }); }
  const box = async (sel) => page.locator(sel).first().boundingBox();
  const stages = await box('#stages'), search = await box('#search'), choose = await box('#choose-open');
  check('phone: the stage cards are in the first screen', stages && stages.y + stages.height <= 844, JSON.stringify(stages));
  check('phone: the search and the chooser button are in the first screen', search && choose && search.y + search.height <= 844 && choose.y + choose.height <= 844, JSON.stringify([search, choose]));
  eq('phone: the chooser button is visible', await page.locator('#choose-open').isVisible(), true);
  const rail = await page.evaluate(() => { const l = document.getElementById('pick-list'); return { row: getComputedStyle(l).flexDirection, scroll: l.scrollWidth > l.clientWidth }; });
  eq('phone: the cards are a horizontal rail', rail, { row: 'row', scroll: true });
  await page.locator('#choose-open').click();
  await page.waitForTimeout(200);
  eq('phone: the chooser opens', await page.evaluate(() => document.getElementById('chooser').open), true);
  eq('phone: the chooser takes focus', (await active(page)).split('/')[0], 'chooser-search');
  const total = data.bursts.length + data.watchlist.top.length + data.watchlist.also_quiet.length;
  eq('phone: the chooser lists every stock', await count(page, '#chooser-list .ss-chooser__item'), total);
  check('phone: the chooser groups by stage', (await text(page, '#chooser-list')).includes('bursts ·') && (await text(page, '#chooser-list')).includes('setting up ·'), 'groups');
  const pick = data.bursts[1] || data.bursts[0];
  await page.fill('#chooser-search', pick.ticker.slice(0, 2).toLowerCase());
  await page.waitForTimeout(100);
  check('phone: the chooser filters', (await count(page, '#chooser-list .ss-chooser__item')) < total || total === 1, 'filter');
  await page.press('#chooser-search', 'Enter');
  await page.waitForTimeout(300);
  eq('phone: Enter chooses the first match', await hash(page), `#/explore/bursts/${pick.ticker}`);
  eq('phone: the chooser closes', await page.evaluate(() => document.getElementById('chooser').open), false);
  eq('phone: focus moves to the chosen stock', (await active(page)).split('/')[0], 'detail');
  eq('phone: the detail is the chosen stock', await text(page, '#detail-h2'), pick.ticker);
  check('phone: the chosen card is pressed', await page.locator(`#pick-list .ss-pick[data-ticker="${pick.ticker}"]`).getAttribute('aria-pressed') === 'true', 'pressed');
  if (shotsDir) { await page.screenshot({ path: path.join(shotsDir, 'full-390-chosen.png') }); await page.screenshot({ path: path.join(shotsDir, 'full-390-chosen-full.png'), fullPage: true }); }
  // Escape closes the chooser and hands focus back to the button that opened it
  await page.locator('#choose-open').click();
  await page.waitForTimeout(150);
  if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'full-390-chooser.png') });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  eq('phone: Escape closes the chooser', await page.evaluate(() => document.getElementById('chooser').open), false);
  eq('phone: focus returns to the chooser button', (await active(page)).split('/')[0], 'choose-open');
  // the back button under the detail head returns to the rail
  await page.locator('#detail .ss-detail__back').click();
  await page.waitForTimeout(200);
  eq('phone: the detail\'s back button focuses the chosen card', (await active(page)).split('/')[2], pick.ticker);
  eq('phone page errors', errors, []);
  await context.close();
  // the reader who asked for less motion gets the same page
  const calm = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { reducedMotion: 'reduce' });
  eq('reduced motion: the page renders', await count(calm.page, '#detail .sc-chart--stock'), 1);
  eq('reduced motion page errors', calm.errors, []);
  await calm.context.close();
  // the desktop's first screen: market context, the stages, the stocks and a meaningful part of the chart
  const desk = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280);
  const d = async (sel) => desk.page.locator(sel).first().boundingBox();
  const bar = await d('#market-bar'), st = await d('#stages'), firstPick = await d('#pick-list .ss-pick'), chart = await d('#chart-mount');
  check('desktop: the market bar, the stages and the first stock are in the first screen', bar && st && firstPick && bar.y >= 0 && st.y + st.height <= 900 && firstPick.y + firstPick.height <= 900, JSON.stringify([bar, st, firstPick]));
  check('desktop: a meaningful part of the chart is in the first screen', chart && chart.y + 220 <= 900, JSON.stringify(chart));
  if (shotsDir) await desk.page.screenshot({ path: path.join(shotsDir, 'full-1280-viewport.png') });
  await desk.context.close();
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
  const trade = data.trades[0];
  for (const [name, now, chipRe, state] of [
    ['pending', PENDING_NOW, /pending/, 'pending'],
    ['pending-after-retry', '2026-09-12T00:30:00Z', /pending/, 'pending'],   // Friday 8:30 PM ET: the retry has just fired
    ['stale1', STALE1_NOW, /STALE · 1 session behind/, 'stale1'],
    ['stale2', STALE2_NOW, /STALE · \d+ sessions behind/, 'stale2']]) {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', now, 1280, { hash: `#/explore/bursts/${trade}` });
    const chip = await text(page, '#status-slot .sc-chip');
    check(`${name} chip`, chipRe.test(chip), chip);
    eq(`${name} state`, await page.getAttribute('html', 'data-ss-rendered'), state);
    check(`${name} next says do not place`, (await text(page, '#next-h3')).startsWith('Do not place these orders'), 'next');
    eq(`${name} cover action falls back to the model plans`, await text(page, '#cover-action'), 'Open model plans');
    if (state !== 'pending') check(`${name} status line links the run log`, (await page.locator('#status-line a[href*="actions/workflows/evening.yml"]').count()) === 1, 'link');
    // the trade's ticket is withheld from the reader's hand, with the setup kept
    eq(`${name} the trade's action area withholds the order`, await page.locator('#detail .ss-action').getAttribute('data-ticket'), 'blocked');
    eq(`${name} no order block`, await count(page, '#detail pre[data-order]'), 0);
    await openAll(page, '#detail details');
    check(`${name} the plan says why`, (await text(page, '#disc-plan')).includes('No order is offered'), 'plan');
    eq(`${name} the order sheet is empty`, await count(page, '#order-sheet tbody tr[data-ticker]'), 0);
    eq(`${name} page errors`, errors, []);
    if (shotsDir && name === 'stale2') await page.screenshot({ path: path.join(shotsDir, 'stale2-1280-dark.png'), fullPage: true });
    await context.close();
  }
  // a fresh record whose run failed before publishing: the record says so
  const failed = JSON.parse(JSON.stringify(data));
  failed.run.status = 'failed';
  const failedPath = '/tests/fixtures/page/.failed.json';
  await mkdir(path.dirname(path.join(ROOT, failedPath)), { recursive: true });
  await writeFile(path.join(ROOT, failedPath), JSON.stringify(failed));
  try {
    const { context, page, errors } = await open(browser, base, failedPath, FRESH_NOW, 1280);
    eq('failed chip', await text(page, '#status-slot .sc-chip'), 'no verdict');
    eq('failed state', await page.getAttribute('html', 'data-ss-rendered'), 'failed');
    eq('failed: no order block', await count(page, '#detail pre[data-order]'), 0);
    eq('failed page errors', errors, []);
    await context.close();
  } finally { await unlink(path.join(ROOT, failedPath)); }
  // a record missing a cosmetic field still renders, with no undefined or NaN in sight
  console.log('-- a field missing');
  for (const field of ['bursts.quality.checks.threshold', 'bursts.quality.checks.label', 'breadth.up4', 'open_plans.entry_ref', 'open_plans.targets', 'run.reads', 'bursts.claude', 'watchlist.top.plan', 'bursts.series', 'bursts.summary', 'watchlist.top.box', 'cash_budget.cut', 'bursts.plan.exit_schedule', 'cover.action_target']) {
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
      await openAll(page, 'details');
      for (const view of ['#/record', '#/market', '#/method', '#/explore']) {
        await go(page, view);
        const body = await page.locator('body').innerText();
        check(`without ${field} nothing prints undefined or NaN on ${view}`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      }
      if (field === 'bursts.series') {
        eq('without bars the first burst shows the chart-unavailable state', await count(page, '#detail [data-chart="unavailable"]'), 1);
        eq('without bars no chart is drawn', await count(page, '#detail .sc-chart--stock'), 0);
        eq('without bars the conditions still stand', await count(page, '#disc-checklist .sc-signal'), data.bursts[0].quality.checks.length);
        await clickPick(page, data.bursts[1].ticker);
        eq('the next burst still has its chart', await count(page, '#detail .sc-chart--stock'), 1);
      }
      eq(`without ${field} page errors`, errors, []);
      await context.close();
    } finally { await unlink(path.join(ROOT, dropPath)); }
  }
  // no record at all: every view says so, and the navigation still works
  const { context, page } = await open(browser, base, '/tests/fixtures/page/does-not-exist.json', FRESH_NOW, 1280);
  eq('missing record h1', await text(page, '#cover-h1'), 'The record could not be read.');
  eq('missing record state', await page.getAttribute('html', 'data-ss-rendered'), 'error');
  check('missing record next', (await text(page, '#next-h3')).startsWith('Do not place any order'), 'next');
  eq('missing record: the detail says so', await count(page, '#detail [data-detail="error"]'), 1);
  eq('missing record: no stages to choose', await count(page, '#stages [data-empty="record"]'), 1);
  await page.locator('#nav a[data-view="record"]').click();
  await page.waitForTimeout(150);
  eq('missing record: the views still switch', await visibleView(page), ['view-record']);
  if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'no-record-1280-dark.png'), fullPage: true });
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
    await checkMobile(browser, base, full);
    await checkStates(browser, base, full);
  } finally {
    await browser.close();
    server.close();
  }
  console.log(`\n${checks - failures}/${checks} page checks passed${shotsDir ? '; screenshots in ' + shotsDir : ''}`);
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
