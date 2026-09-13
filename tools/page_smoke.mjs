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
// --only <name[,name]> runs just those suites (variant names, or lens/compare/
// evidence/map/mobile/modes/following/volume/mapscale/ticket/states). It is for
// judging a mutant in a minute; CI and the milestone gate run everything.
const only = args.includes('--only') ? String(args[args.indexOf('--only') + 1] || '').split(',').filter(Boolean) : null;
const runs = (name) => !only || only.includes(name);

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
  const context = await browser.newContext({ viewport: { width, height: opts.height || 900 }, colorScheme: opts.theme || 'dark', reducedMotion: opts.reducedMotion || 'no-preference', hasTouch: !!opts.touch, permissions: ['clipboard-read', 'clipboard-write'] });
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
  await page.addInitScript(({ dataUrl, now, theme, lens, sort }) => {
    window.SCStock = { dataUrl, now };
    if (theme) try { localStorage.setItem('sc-theme', theme); } catch (e) { /* no storage */ }
    // seed the reader's remembered lens the way the page itself stores it, so a
    // suite about something else opens on the whole stage rather than a subset
    if (lens || sort) try { localStorage.setItem('spicystock:lens:v1', JSON.stringify({ bursts: lens || null, 'setting-up': lens || null, sort: sort || null })); } catch (e) { /* no storage */ }
  }, { dataUrl, now, theme: opts.theme, lens: opts.lens || null, sort: opts.sort || null });
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
const pctOf = (v, dec = 1) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dec) + '%';   // the page's pct()
const hash = (page) => page.evaluate(() => location.hash);
const go = async (page, h) => { await page.evaluate((h) => { location.hash = h; }, h); await page.waitForTimeout(120); };
const visibleView = (page) => page.evaluate(() => Array.from(document.querySelectorAll('.ss-view')).filter((s) => !s.hidden).map((s) => s.id));
const openAll = (page, sel) => page.evaluate((sel) => document.querySelectorAll(sel).forEach((d) => { d.open = true; }), sel);
const active = (page) => page.evaluate(() => { const a = document.activeElement; return a ? (a.id || '') + '/' + (a.className || '') + '/' + (a.dataset ? a.dataset.ticker || '' : '') : ''; });
const clickPick = async (page, ticker) => { await page.locator(`#pick-list .ss-pick[data-ticker="${ticker}"]`).click(); await page.waitForTimeout(150); };
// the lens: the page opens on A-quality when the record archived an A or A+
// burst and on every burst otherwise (docs/app.js defaultLens(); the smoke
// works it out again, off the record, rather than reading the page's answer)
const openingLens = (data) => ((data.bursts || []).some((b) => TRADE_GRADES.includes(b.grade)) ? 'a' : 'all');
const lensNow = (page) => page.locator('#lens .sc-tab[aria-pressed="true"]').first().getAttribute('data-lens');
const setLens = async (page, lens) => { await page.locator(`#lens .sc-tab[data-lens="${lens}"]`).click(); await page.waitForTimeout(180); };
const cardTickers = (page) => page.locator('#pick-list .ss-pick').evaluateAll((els) => els.map((e) => e.dataset.ticker));

// the Setup range: the base and a short run of context before it, as docs/app.js frames it (the smoke computes it again, on its own)
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const dateWords = (iso) => { const dt = new Date(iso + 'T12:00:00Z'); return WD[dt.getUTCDay()] + ' ' + dt.getUTCDate() + ' ' + MON[dt.getUTCMonth()]; }; // the page's spelling
function setupSessions(series, base) {
  const bs = base && base.start ? series.findIndex((x) => x.date === base.start) : -1, be = base && base.end ? series.findIndex((x) => x.date === base.end) : -1;
  if (bs < 0 || be < bs) return Math.min(60, series.length);
  const pad = Math.max(8, Math.round((be - bs + 1) * 0.6));
  return series.length - Math.max(0, bs - pad);
}
// the volume ratio the page reads for a burst: the row's own field, else the checklist's two-place copy;
// a finite number of zero or more, else null (docs/app.js volumeRatio(); the smoke reads it again, on its own)
const ratioOf = (b) => { const own = b.volume_vs_prior, q = b.quality && b.quality.burst ? b.quality.burst.volume_vs_prior : null; return typeof own === 'number' && isFinite(own) && own >= 0 ? own : typeof q === 'number' && isFinite(q) && q >= 0 ? q : null; };
const times = (v) => v === null ? '—' : v.toFixed(1);
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
    eq(`${variant} ${b.ticker} opens on the Setup range`, await chart.getAttribute('data-range'), 'setup');
    eq(`${variant} ${b.ticker} the Setup range frames the base`, +(await chart.getAttribute('data-sessions')), setupSessions(b.series, b.quality.base));
    check(`${variant} ${b.ticker} burst legend`, (await text(page, '#detail .sc-legend')).includes('burst'), 'legend');
    eq(`${variant} ${b.ticker} one chart panel with three modes and three ranges`, [await count(page, '#detail .ss-chart-panel'), await count(page, '#detail .sc-tab[data-mode]'), await count(page, '#detail .sc-tab[data-range]')], [1, 3, 3]);
    const refs = await text(page, '#detail [data-refs]');
    if (b.plan) {
      check(`${variant} ${b.ticker} reference line names the stop, the trigger and the limit`, refs.includes('stop ' + usd(b.plan.stop)) && refs.includes('trigger ' + usd(b.plan.entry_ref)) && refs.includes('limit ' + usd(b.plan.entry_high)), refs);
      const shown = b.series.slice(-setupSessions(b.series, b.quality.base)), top = Math.max(...shown.map((x) => x.h));
      eq(`${variant} ${b.ticker} says when the aim is outside the visible range`, refs.includes('outside the visible range'), b.plan.targets.high > top);
    }
    check(`${variant} ${b.ticker} chart range is disclosed`, /^Showing \d+ sessions, .+ – .+ \d{4} · /.test(await text(page, '#detail .ss-chart-panel__range')), await text(page, '#detail .ss-chart-panel__range'));
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
  const btn = await text(page, '#detail .ss-action > button[data-open]');
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
  check(`${variant} ${b.ticker} conditions carry the gain and the volume`, conditions.includes(`+${b.gain_pct.toFixed(1)}%`) && conditions.includes(times(ratioOf(b)) + '× volume'), conditions.slice(0, 200));
  if (b.scan === 'dollar') check(`${variant} ${b.ticker} a $-only day carries its volume ratio like any other`, ratioOf(b) !== null && ratioOf(b) === b.volume_vs_prior && conditions.includes(times(ratioOf(b)) + '× volume') && !conditions.includes('read from the checklist'), [b.volume_vs_prior, conditions.slice(0, 120)]);
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
  if (status !== 'ticket' || blocked) check(`${variant} ${b.ticker} plan says why there is no order`, /No ticket tonight|Ticket withheld|No order is offered|No plan/.test(planText), planText.slice(-200));
  // and never says it twice: the lead and the record's own reason are one sentence
  if (status !== 'ticket') check(`${variant} ${b.ticker} plan says it once`, !/no ticket\W{0,4}no ticket|No ticket tonight: ticket withheld/i.test(planText), planText.slice(-200));
  // provenance
  const prov = await text(page, '#disc-provenance');
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} claude read`, prov.includes(b.claude.reason), 'reason');
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} a fixture's reader reply is labelled simulated`, prov.includes('simulated chart-reader reply') && !prov.includes('claude read the chart'), prov.slice(0, 120));
  if ((b.series || []).length) check(`${variant} ${b.ticker} chart panel carries the demo chip`, (await text(page, '#detail .ss-chart-panel__head')).includes('demo data'), 'chip');
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
  // a fixture is sample data and says so, everywhere it could be mistaken for a live record
  eq(`${variant} the page marks the fixture as demo data`, await page.getAttribute('html', 'data-ss-demo'), 'true');
  check(`${variant} the sample-data warning is shown`, (await text(page, '#demo-notice')).includes('Do not trade sample data'), await text(page, '#demo-notice'));
  check(`${variant} the sample-data notice names the fixture`, (await text(page, '#demo-notice')).includes('fixture ' + data.fixture), await text(page, '#demo-notice'));
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
    // the lens this record opens on, and the A-quality subset it shows; the
    // walk below is of the whole stage, so it is widened first
    eq(`${variant} opens on the lens the record earns`, await lensNow(page), openingLens(data));
    eq(`${variant} the A-quality lens is exactly the archived A and A+ grades`,
      openingLens(data) === 'a' ? await cardTickers(page) : null,
      openingLens(data) === 'a' ? data.bursts.filter((b) => TRADE_GRADES.includes(b.grade)).map((b) => b.ticker) : null);
    await setLens(page, 'all');
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
      await page.locator('#detail .ss-action > button[data-open]').click();
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
  // every cut is named with its own reason, and the reason is given ONCE: the
  // budget's reason for a plan the stop rule withheld already opens with
  // "ticket withheld", so the line does not introduce it with "No ticket" too
  for (const c of data.cash_budget.cut) {
    const leads = /^(no ticket|ticket withheld)/i.test(c.reason);
    check(`${variant} cut ${c.ticker} explained`,
      budget.includes(leads ? `${c.ticker} — ${c.reason}` : `No ticket: ${c.ticker}`) && budget.includes(c.reason), budget);
  }
  check(`${variant} the budget says it once`, !/no ticket\W{0,4}(no ticket|ticket withheld)/i.test(budget), budget);
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
  // the stage card's sub-line is where a stage says how many of its stocks
  // carry a ticket; a phone that drops it loses the action state entirely
  const phoneStages = await page.locator('#stages .ss-stage__sub').evaluateAll((els) => els.map((e) =>
    ({ text: e.innerText.replace(/\s+/g, ' ').trim(), drawn: e.getClientRects().length > 0 })));   // innerText reads a display:none element too; the rects do not
  check('phone: each stage card still draws how many carry a ticket', phoneStages.length === 2 && phoneStages.every((s) => s.drawn && /\d+ with a ticket/.test(s.text)), JSON.stringify(phoneStages));
  // the action bar is the system's .sc-actionbar: stacked on a phone, with the
  // sentence keeping only the height its own text needs. A flex-basis written
  // for a row becomes a HEIGHT in a column and buries the button under an
  // empty band -- 260px of it, measured on this page before the bar was shared.
  const actionGeom = await page.evaluate(() => {
    const bar = document.querySelector('#detail .ss-action');
    if (!bar) return null;
    const p = bar.querySelector('p'), btn = bar.querySelector('button[data-open]');
    if (!p || !btn) return null;
    const range = document.createRange(); range.selectNodeContents(p);
    const text = range.getBoundingClientRect(), pbox = p.getBoundingClientRect(), bbox = btn.getBoundingClientRect(), bar0 = bar.getBoundingClientRect();
    const cs = getComputedStyle(bar);
    return { column: cs.flexDirection === 'column', box: Math.round(pbox.height), text: Math.round(text.height),
      toButton: Math.round(bbox.top - text.bottom), button: Math.round(bbox.width), bottom: Math.round(bbox.bottom),
      content: Math.round(bar0.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)) };
  });
  check('phone: the action bar stacks and its sentence keeps its own height', actionGeom && actionGeom.column && actionGeom.box <= actionGeom.text + 6, JSON.stringify(actionGeom));
  check('phone: no empty band between the sentence and the action', actionGeom && actionGeom.toButton >= 0 && actionGeom.toButton <= 32, JSON.stringify(actionGeom));
  check('phone: the action spans the bar', actionGeom && actionGeom.button >= actionGeom.content - 2, JSON.stringify(actionGeom));
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
  const deskStages = await desk.page.locator('#stages .ss-stage__sub').evaluateAll((els) => els.map((e) =>
    ({ text: e.innerText.replace(/\s+/g, ' ').trim(), drawn: e.getClientRects().length > 0 })));
  eq('the phone and the desktop stage cards carry the same ticket counts', phoneStages, deskStages);
  const bar = await d('#market-bar'), st = await d('#stages'), firstPick = await d('#pick-list .ss-pick'), chart = await d('#chart-mount');
  check('desktop: the market bar, the stages and the first stock are in the first screen', bar && st && firstPick && bar.y >= 0 && st.y + st.height <= 900 && firstPick.y + firstPick.height <= 900, JSON.stringify([bar, st, firstPick]));
  check('desktop: a meaningful part of the chart is in the first screen', chart && chart.y + 220 <= 900, JSON.stringify(chart));
  if (shotsDir) await desk.page.screenshot({ path: path.join(shotsDir, 'full-1280-viewport.png') });
  await desk.context.close();
}


// the three modes over one stock: identical levels, dates and tooltip values; the range and the mode remembered; one chart at a time
async function checkModes(browser, base, data) {
  console.log('-- the chart modes');
  const coil = data.watchlist.top.find((r) => r.ticker === 'COIL') || data.watchlist.top[0];
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/setting-up/${coil.ticker}` });
  const read = () => page.evaluate(() => {
    const host = document.querySelector('#chart-mount .sc-chart--stock'), svg = host.querySelector('svg');
    const level = (k) => { const l = svg.querySelector(`[data-level="${k}"]`); return l ? l.getAttribute('y1') : null; };
    return { mode: host.getAttribute('data-mode'), range: host.getAttribute('data-range'), sessions: host.getAttribute('data-sessions'), stop: level('stop'), trigger: level('trigger'), close: level('close'),
      labels: Array.from(svg.querySelectorAll('text[data-kind]')).map((t) => t.getAttribute('data-kind') + ':' + t.textContent + '@' + t.getAttribute('y')), hosts: document.querySelectorAll('.sc-chart--stock').length,
      candles: svg.querySelectorAll('.sc-chart__candle').length, closePath: svg.querySelectorAll('path[data-series="close"]').length, dates: Array.from(svg.querySelectorAll('text')).filter((t) => /^\d+ \w{3}$/.test(t.textContent)).map((t) => t.textContent).join(','),
      tones: { up: (svg.querySelector('.sc-chart__candle:not(.is-filled)') || { parentNode: { getAttribute: () => '' } }).parentNode.getAttribute('style'), down: (svg.querySelector('.sc-chart__candle.is-filled') || { parentNode: { getAttribute: () => '' } }).parentNode.getAttribute('style') },
      levelsTable: Array.from(document.querySelectorAll('#chart-mount [data-sc-twin="levels"] tbody tr')).map((r) => r.textContent.replace(/\s+/g, ' ').trim()).join(' | ') };
  });
  const hover = async () => { await page.locator('#chart-mount .sc-chart__hit').scrollIntoViewIfNeeded(); const box = await page.locator('#chart-mount .sc-chart__hit').boundingBox(); await page.mouse.move(box.x - 2, box.y - 2); await page.mouse.move(box.x + box.width * 0.35, box.y + box.height / 2); await page.waitForTimeout(120); return (await page.locator('#chart-mount .sc-tooltip').innerText().catch(() => '')).replace(/\s+/g, ' '); };
  // the two segmented groups in the panel's strip: each visibly captioned, and
  // its caption is the group's accessible name -- "setup" is a mode AND a
  // range, so an uncaptioned row cannot be told from the one beside it
  const groups = await page.evaluate(() => Array.from(document.querySelectorAll('#detail .ss-chart-panel__tools .sc-tabs')).map((g) => {
    const id = g.getAttribute('aria-labelledby'), label = id ? document.getElementById(id) : null;
    return { kind: g.querySelector('.sc-tab') ? (g.querySelector('.sc-tab').dataset.mode ? 'mode' : 'range') : '?',
      caption: label ? label.textContent.trim() : null, visible: !!(label && label.getClientRects().length),
      captioned: !!(label && g.closest('.sc-field--group') && g.closest('.sc-field--group').contains(label)),
      ariaLabel: g.getAttribute('aria-label'), buttons: Array.from(g.querySelectorAll('.sc-tab')).map((b) => b.textContent.trim().toLowerCase()) };
  }));
  eq('the chart strip has two captioned groups', await count(page, '#detail .ss-chart-panel__tools .sc-field--group .sc-tabs'), 2);
  check('each chart control group names a caption the reader can see', groups.every((g) => g.caption && g.visible && g.captioned && !g.ariaLabel), JSON.stringify(groups));
  check('the two captions differ, though a button word is in both', groups[0] && groups[1] && groups[0].caption !== groups[1].caption
    && groups[0].buttons.some((b) => groups[1].buttons.includes(b)), JSON.stringify(groups.map((g) => [g.caption, g.buttons])));
  const seen = {};
  for (const mode of ['setup', 'candles', 'line']) {
    await page.click(`#detail .sc-tab[data-mode="${mode}"]`); await page.waitForTimeout(150);
    seen[mode] = await read(); seen[mode].tip = await hover();
    eq(`mode ${mode} is drawn`, seen[mode].mode, mode);
    eq(`mode ${mode} keeps one chart host`, seen[mode].hosts, 1);
  }
  for (const mode of ['candles', 'line']) {
    eq(`${mode} shares the stop, trigger and close coordinates with setup`, [seen[mode].stop, seen[mode].trigger, seen[mode].close], [seen.setup.stop, seen.setup.trigger, seen.setup.close]);
    eq(`${mode} shares the gutter labels with setup`, seen[mode].labels, seen.setup.labels);
    eq(`${mode} shares the dates with setup`, seen[mode].dates, seen.setup.dates);
    eq(`${mode} shares the level table with setup`, seen[mode].levelsTable, seen.setup.levelsTable);
    eq(`${mode} shares the tooltip values with setup`, seen[mode].tip, seen.setup.tip);
  }
  check('the tooltip reads open, high, low, close and volume', /open/.test(seen.setup.tip) && /volume/.test(seen.setup.tip), seen.setup.tip);
  check('the line mode draws the closes and no candle', seen.line.closePath === 1 && seen.line.candles === 0, `${seen.line.closePath}/${seen.line.candles}`);
  // the tones need a down bar, which the coil's flat fixture lacks: a burst with one in its last 60 sessions
  const downBurst = data.bursts.find((b) => (b.series || []).slice(-60).some((bar) => bar.c < bar.o));
  await go(page, `#/explore/bursts/${downBurst.ticker}`); await page.click('#detail .sc-tab[data-range="60"]'); await page.waitForTimeout(150);
  await page.click('#detail .sc-tab[data-mode="candles"]'); await page.waitForTimeout(150); const tCandles = await read();
  await page.click('#detail .sc-tab[data-mode="setup"]'); await page.waitForTimeout(150); const tSetup = await read();
  check('candles are colour-coded up and down, and hollow versus filled', /--sc-good/.test(tCandles.tones.up) && /--sc-danger/.test(tCandles.tones.down) && tCandles.candles > 0, JSON.stringify(tCandles.tones));
  check('setup mode draws candles in the chart tones', /chart-emphasis/.test(tSetup.tones.up) && /chart-context/.test(tSetup.tones.down), JSON.stringify(tSetup.tones));
  await page.click('#detail .sc-tab[data-mode="line"]'); await go(page, `#/explore/setting-up/${coil.ticker}`); await page.click('#detail .sc-tab[data-range="setup"]'); await page.waitForTimeout(150); // back where the loop left off: line mode, the setup range
  // the COIL cluster reads apart: four level labels, none closer than a label's height
  const cluster = seen.setup.labels.filter((l) => /^(stop|trigger|limit|close):/.test(l)).map((l) => +l.split('@')[1]).sort((a, b) => a - b);
  eq('the COIL cluster has its four labels', cluster.length, 4);
  check('the COIL cluster labels never overlap', cluster.every((y, i) => !i || y - cluster[i - 1] >= 14), cluster.join(','));
  check('the COIL levels are the reference values', seen.setup.labels.join(' ').includes('stop $109.50') && seen.setup.labels.join(' ').includes('trigger $110.61') && seen.setup.labels.join(' ').includes('limit $111.72') && seen.setup.labels.join(' ').includes('close:$110.00'), seen.setup.labels.join(' '));
  // the range: 60 and 120 disclose their dates; setup frames the box; the mode holds across ranges and stocks
  await page.click('#detail .sc-tab[data-range="60"]'); await page.waitForTimeout(150);
  let r = await read();
  eq('60 sessions shows 60', [r.sessions, r.mode], ['60', 'line']);
  check('the range sentence discloses the dates', /Showing 60 sessions, .+ – .+ 2026 · the last 60 sessions\./.test(await text(page, '#detail .ss-chart-panel__range')), await text(page, '#detail .ss-chart-panel__range'));
  await page.click('#detail .sc-tab[data-range="setup"]'); await page.waitForTimeout(150);
  r = await read();
  eq('the Setup range frames the coil', +r.sessions, setupSessions(coil.series, coil.box));
  await clickPick(page, coil.ticker);
  await go(page, `#/explore/bursts/${data.trades[0]}`);
  r = await read();
  eq('the mode and the range hold across stocks', [r.mode, r.range], ['line', 'setup']);
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(250);
  r = await read();
  eq('the mode and the range hold across a reload', [r.mode, r.range], ['line', 'setup']);
  // rapid switching: modes and stocks in a burst of clicks, one chart at the end, the right one
  for (const b of data.bursts) { await page.locator(`#pick-list .ss-pick[data-ticker="${b.ticker}"]`).click({ noWaitAfter: true }); for (const m of ['setup', 'candles', 'line']) await page.locator(`#detail .sc-tab[data-mode="${m}"]`).click({ noWaitAfter: true }).catch(() => {}); }
  await page.waitForTimeout(400);
  const lastB = data.bursts[data.bursts.length - 1];
  r = await read();
  eq('rapid mode and stock switching ends with one chart of the last stock', [r.hosts, await page.locator('#chart-mount .sc-chart--stock').getAttribute('data-ticker'), await text(page, '#detail-h2')], [1, lastB.ticker, lastB.ticker]);
  await page.click('#detail .sc-tab[data-mode="setup"]');
  eq('mode journey page errors', errors, []);
  if (shotsDir) {
    await go(page, `#/explore/setting-up/${coil.ticker}`);
    for (const mode of ['setup', 'candles', 'line']) { await page.click(`#detail .sc-tab[data-mode="${mode}"]`); await page.waitForTimeout(150); await page.locator('#detail .ss-chart-panel').screenshot({ path: path.join(shotsDir, `chart-${coil.ticker}-${mode}-1280.png`) }); }
    await page.click('#detail .sc-tab[data-mode="setup"]');
    await go(page, `#/explore/bursts/${data.trades[0]}`); await page.waitForTimeout(150);
    await page.locator('#detail .ss-chart-panel').screenshot({ path: path.join(shotsDir, `chart-${data.trades[0]}-setup-1280.png`) });
  }
  await context.close();
  // the phone: the cluster still reads apart at 390px
  const m = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844, lens: 'all', hash: `#/explore/setting-up/${coil.ticker}` });
  const ml = await m.page.evaluate(() => Array.from(document.querySelectorAll('#chart-mount svg text[data-kind]')).filter((t) => /^(stop|trigger|limit|close)$/.test(t.getAttribute('data-kind'))).map((t) => +t.getAttribute('y')).sort((a, b) => a - b));
  eq('phone: the COIL cluster has its four labels', ml.length, 4);
  check('phone: the COIL cluster labels never overlap', ml.every((y, i) => !i || y - ml[i - 1] >= 14), ml.join(','));
  const svgBox = await m.page.locator('#chart-mount svg').boundingBox(), hostBox = await m.page.locator('#chart-mount').boundingBox();
  check('phone: the chart does not overflow its panel', svgBox && hostBox && svgBox.width <= hostBox.width + 1, JSON.stringify([svgBox, hostBox]));
  if (shotsDir) await m.page.locator('#detail .ss-chart-panel').screenshot({ path: path.join(shotsDir, `chart-${coil.ticker}-setup-390.png`) });
  eq('phone mode page errors', m.errors, []);
  await m.context.close();
}

// the burst map: the recorded measurements, one selection with the cards, the chooser and the route
async function checkMap(browser, base, data) {
  console.log('-- the burst map');
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all' });
  const plottable = data.bursts.filter((b) => typeof b.gain_pct === 'number' && ratioOf(b) !== null);
  eq('every burst of the fixture has a ratio the page can read', plottable.length, data.bursts.length);
  eq('the Cards | Map control is offered for the bursts', await page.locator('#discover').isVisible(), true);
  await page.click('#discover .sc-tab[data-discover="map"]'); await page.waitForTimeout(300);
  eq('map mode lays the map across the workspace', await page.getAttribute('#workspace', 'data-discover'), 'map');
  eq('one point per burst with both measurements', await count(page, '#burst-map .ss-map__point'), plottable.length);
  const pts = await page.locator('#burst-map .ss-map__point').evaluateAll((els) => els.map((e) => [e.dataset.ticker, +e.dataset.gain, +e.dataset.volume, e.getAttribute('aria-pressed')]));
  for (const b of plottable) { const p = pts.find((x) => x[0] === b.ticker); eq(`${b.ticker} is plotted at its recorded gain and volume ratio`, p && [p[1], p[2]], [b.gain_pct, ratioOf(b)]); }
  check('the map names the session and the counts', (await text(page, '#burst-map .ss-map__stamp')).includes('session ' + dateWords(data.run.session)) && (await text(page, '[data-counts]')).includes(`${data.bursts.length} bursts · ${plottable.length} plotted`), await text(page, '[data-counts]'));
  check('the axes name the exact measurements and say which is compressed', (await text(page, '#burst-map')).includes('Volume vs previous session (×, compressed)') && (await text(page, '#burst-map')).includes('Gain on the session vs previous close (%)'), 'axes');
  check('the map says position is a measurement, not a return', (await text(page, '#burst-map .ss-map__note')).includes('not a predicted return'), 'note');
  eq('the first burst is the selected point', pts.filter((p) => p[3] === 'true').map((p) => p[0]), [data.bursts[0].ticker]);
  const other = plottable[plottable.length - 1];
  await page.click(`#burst-map .ss-map__point[data-ticker="${other.ticker}"]`); await page.waitForTimeout(250);
  eq('a point opens the same detail as a card', [await hash(page), await text(page, '#detail-h2')], [`#/explore/bursts/${other.ticker}`, other.ticker]);
  check('the selection line describes the chosen point with its source and status', (await text(page, '#burst-map .ss-map__selection')).startsWith(other.ticker + ':'), await text(page, '#burst-map .ss-map__selection'));
  const rowsInTable = await count(page, '#burst-map .ss-map__table tbody tr');
  eq('the table twin lists every burst', rowsInTable, data.bursts.length);
  // the keyboard: arrows move between points in rank order, Enter chooses
  await page.locator(`#burst-map .ss-map__point[data-ticker="${plottable[0].ticker}"]`).focus();
  await page.keyboard.press('ArrowRight');
  eq('ArrowRight moves focus to the next point', await page.evaluate(() => document.activeElement.dataset.ticker), plottable[1].ticker);
  await page.keyboard.press('Enter'); await page.waitForTimeout(250);
  eq('Enter chooses the focused point', await text(page, '#detail-h2'), plottable[1].ticker);
  // search and the chooser highlight the same point
  await page.fill('#search', other.ticker.toLowerCase()); await page.press('#search', 'Enter'); await page.waitForTimeout(250);
  eq('a search selection highlights its point', await page.locator(`#burst-map .ss-map__point[data-ticker="${other.ticker}"]`).getAttribute('aria-pressed'), 'true');
  await page.goBack(); await page.waitForTimeout(250);
  eq('Back keeps the map and restores the point', [await page.getAttribute('#workspace', 'data-discover'), await page.locator(`#burst-map .ss-map__point[data-ticker="${plottable[1].ticker}"]`).getAttribute('aria-pressed')], ['map', 'true']);
  await page.click('#discover .sc-tab[data-discover="cards"]'); await page.waitForTimeout(200);
  eq('Cards restores the list with the same stock chosen', [await count(page, '#burst-map'), (await page.locator('#pick-list .ss-pick[aria-pressed="true"]').getAttribute('data-ticker'))], [0, plottable[1].ticker]);
  await page.click('#discover .sc-tab[data-discover="map"]'); await page.waitForTimeout(200);
  await page.locator('#stages .ss-stage[data-stage="setting-up"]').click(); await page.waitForTimeout(200);
  eq('Setting up is never mapped', [await page.locator('#discover').isVisible(), await count(page, '#burst-map')], [false, 0]);
  await page.locator('#stages .ss-stage[data-stage="bursts"]').click(); await page.waitForTimeout(200);
  eq('the map returns with the bursts', await count(page, '#burst-map .ss-map__point'), plottable.length);
  eq('map page errors', errors, []);
  if (shotsDir) { await page.locator('#burst-map').screenshot({ path: path.join(shotsDir, 'map-1280.png') }); await page.screenshot({ path: path.join(shotsDir, 'map-page-1280.png') }); }
  await context.close();
  const m = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844, lens: 'all' });
  await m.page.click('#discover .sc-tab[data-discover="map"]'); await m.page.waitForTimeout(300);
  eq('phone: the map is drawn', await count(m.page, '#burst-map .ss-map__point'), plottable.length);
  const mb = await m.page.locator('#burst-map').boundingBox();
  check('phone: the map does not overflow the screen', mb && mb.x >= 0 && mb.x + mb.width <= 390, JSON.stringify(mb));
  if (shotsDir) await m.page.locator('#burst-map').screenshot({ path: path.join(shotsDir, 'map-390.png') });
  eq('phone map page errors', m.errors, []);
  await m.context.close();
}

// Following: one click saves the setup with its suggested size; an edit survives a reload; nothing public changes
async function checkFollowing(browser, base, data) {
  console.log('-- following');
  const trade = data.bursts.find((b) => b.ticker === data.trades[0]);
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { hash: `#/explore/bursts/${trade.ticker}` });
  const publicBefore = await page.evaluate(() => JSON.stringify([SCStock.data.scorecard, SCStock.data.trades, SCStock.data.cash_budget, SCStock.data.bursts.map((b) => b.plan && b.plan.order_line)]));
  eq('nothing followed yet', await text(page, '#following-jump'), 'Following · 0');
  check('the follow button names the suggested size', (await text(page, '#detail .ss-follow')).includes(`${trade.plan.shares} shares suggested`), await text(page, '#detail .ss-follow'));
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('one click follows', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'following');
  eq('the shelf shows the setup', await count(page, `#following .ss-followed[data-ticker="${trade.ticker}"]`), 1);
  eq('the count control moves', await text(page, '#following-jump'), 'Following · 1');
  const card = () => text(page, `#following .ss-followed[data-ticker="${trade.ticker}"]`);
  check('the card keeps the saved plan levels', (await card()).includes('stop ' + usd(trade.plan.stop)) && (await card()).includes('limit ' + usd(trade.plan.entry_high)), await card());
  check('the card shows the latest close with its date and no newer observation', (await card()).includes(usd(trade.close)) && (await card()).includes('no newer observation available'), await card());
  const ownWords = () => page.locator(`#following .ss-followed[data-ticker="${trade.ticker}"]`).first().evaluate((c) => { const k = c.cloneNode(true); k.querySelectorAll('.ss-followed__note').forEach((n) => n.remove()); return k.innerText; });
  check('the card never asserts a fill or a holding in its own words', !/\b(bought|filled|held|sold|stopped out)\b/i.test(await ownWords()), await ownWords());
  check('the record’s sentence on the card is quoted and labelled as the record’s', /the (record|model plan) says\s*“/.test(await card()), await card());
  await page.click('#detail .ss-follow button[data-follow-action="add"]').catch(() => {});
  eq('a second click is idempotent', await count(page, '#following .ss-followed'), 1);
  await page.click('#detail .ss-follow button[data-follow-action="edit"]');
  await page.fill('#detail .ss-follow__form input', '0'); await page.click('#detail .ss-follow__form button[type="submit"]'); await page.waitForTimeout(150);
  check('an invalid size is refused with a sentence', (await text(page, '#detail .ss-follow')).includes('whole number of shares'), await text(page, '#detail .ss-follow'));
  await page.fill('#detail .ss-follow__form input', String(trade.plan.shares + 2)); await page.click('#detail .ss-follow__form button[type="submit"]'); await page.waitForTimeout(200);
  check('the reference size is labelled as the reader’s', (await text(page, '#detail .ss-follow')).includes(`your reference size ${trade.plan.shares + 2} shares (plan suggested ${trade.plan.shares})`), await text(page, '#detail .ss-follow'));
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(250);
  check('the edit survives a reload', (await text(page, '#detail .ss-follow')).includes(`your reference size ${trade.plan.shares + 2} shares`), await text(page, '#detail .ss-follow'));
  eq('the store is the demo store for a fixture', await page.evaluate(() => Object.keys(localStorage).filter((k) => /following/.test(k))), ['spicystock:following:demo:v1']);
  const publicAfter = await page.evaluate(() => JSON.stringify([SCStock.data.scorecard, SCStock.data.trades, SCStock.data.cash_budget, SCStock.data.bursts.map((b) => b.plan && b.plan.order_line)]));
  eq('following changes nothing public', publicAfter, publicBefore);
  // a newer record: the observation moves, the saved plan does not
  const newer = JSON.parse(JSON.stringify(data));
  newer.observations.symbols[trade.ticker] = { date: '2026-09-11', o: 126, h: 131, l: 125, c: 130, v: 1000, since: data.run.session };
  await page.evaluate((d) => { SCStock.render(d, new Date('2026-09-10T22:31:00Z')); }, newer);
  await page.waitForTimeout(250);
  check('a newer observation updates the card', (await card()).includes('$130.00') && (await card()).includes('11 Sep') && (await card()).includes('since the signal'), await card());
  check('the saved plan is unchanged by the newer record', (await card()).includes('stop ' + usd(trade.plan.stop)) && (await card()).includes(`your reference size ${trade.plan.shares + 2} shares`), await card());
  check('the movement is labelled as price movement, not a result', (await card()).includes('not your result'), await card());
  // a withheld setup can be followed for observation, without a size
  const withheld = (data.cash_budget.cut || []).find((c) => c.kind === 'withheld');
  if (withheld) {
    await go(page, `#/explore/bursts/${withheld.ticker}`);
    const hint = await text(page, '#detail .ss-follow');
    check('a withheld setup offers observation only', hint.includes('for observation, ticket withheld') && hint.includes('saved in this browser only'), hint);
    check('the observation hint names the reason once', (hint.match(/ticket withheld/gi) || []).length === 1 && !/no ticket/i.test(hint), hint);
    await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
    check('the withheld reason stays beside the followed setup', (await text(page, '#detail .ss-action')).includes('ticket withheld') && (await text(page, `#following .ss-followed[data-ticker="${withheld.ticker}"]`)).includes('observation only, no size'), 'withheld');
    await page.click('#detail .ss-follow button[data-follow-action="remove"]'); await page.waitForTimeout(150);
  }
  await go(page, `#/explore/bursts/${trade.ticker}`);
  await page.click('#detail .ss-follow button[data-follow-action="remove"]'); await page.waitForTimeout(200);
  eq('undo removes the setup', [await page.locator('#detail .ss-follow').getAttribute('data-follow'), await count(page, '#following .ss-followed'), await text(page, '#following-jump')], ['not-following', 0, 'Following · 0']);
  // a blocked write says so and never shows Following
  await page.evaluate(() => { window.__setItem = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error('blocked'); }; });
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('a blocked write is not a follow', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'not-following');
  check('a blocked write is named', (await text(page, '#detail .ss-follow')).includes('Could not save in this browser'), await text(page, '#detail .ss-follow'));
  eq('following page errors', errors, []);
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('a second blocked write does not stack its sentence', await count(page, '#detail .ss-follow .ss-follow__warn'), 1);
  await page.evaluate(() => { Storage.prototype.setItem = window.__setItem; });
  if (shotsDir) { await go(page, `#/explore/bursts/${trade.ticker}`); await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200); eq('the store works again once unblocked', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'following'); await page.locator('#detail .ss-action').screenshot({ path: path.join(shotsDir, 'follow-action-1280.png') }); await page.locator('#following').screenshot({ path: path.join(shotsDir, 'following-1280.png') }); }
  await context.close();
  // a corrupt store is set aside, named, and starts empty
  const c2 = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { hash: `#/explore/bursts/${trade.ticker}` });
  await c2.page.evaluate(() => { localStorage.setItem('spicystock:following:demo:v1', '{not json'); SCStock.render(SCStock.data, new Date('2026-09-10T22:31:00Z')); });
  await c2.page.waitForTimeout(200);
  check('a corrupt store is set aside and named', (await text(c2.page, '#following-status')).includes('could not be read') && (await c2.page.evaluate(() => localStorage.getItem('spicystock:following:demo:v1.corrupt'))) === '{not json', await text(c2.page, '#following-status'));
  eq('corrupt-store page errors', c2.errors, []);
  await c2.context.close();
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
  for (const field of ['bursts.quality.checks.threshold', 'bursts.quality.checks.label', 'breadth.up4', 'open_plans.entry_ref', 'open_plans.targets', 'run.reads', 'bursts.claude', 'watchlist.top.plan', 'bursts.series', 'bursts.summary', 'watchlist.top.box', 'cash_budget.cut', 'bursts.plan.exit_schedule', 'cover.action_target', 'bursts.quality.base', 'bursts.volume_vs_prior', 'observations']) {
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
      if (field === 'bursts.quality.base') {
        check('without base dates the Setup range says so and falls back', (await text(page, '#detail .ss-chart-panel__range')).includes('Setup range unavailable'), await text(page, '#detail .ss-chart-panel__range'));
        eq('without base dates the fallback shows 60 sessions', await page.locator('#detail .sc-chart--stock').getAttribute('data-sessions'), String(Math.min(60, data.bursts[0].series.length)));
      }
      if (field === 'bursts.volume_vs_prior') {
        // a record from before the dollar scan carried the ratio: the row's own field is null and the
        // checklist's two-place copy stands in -- plotted, printed everywhere, and said to be the checklist's
        const first = data.bursts[0], q = first.quality.burst.volume_vs_prior;
        await page.click('#discover .sc-tab[data-discover="map"]'); await page.waitForTimeout(250);
        eq('without the row’s own ratio the checklist’s copy plots the burst', await page.locator(`#burst-map .ss-map__point[data-ticker="${first.ticker}"]`).evaluateAll((els) => els.map((e) => [+e.dataset.gain, +e.dataset.volume])), [[first.gain_pct, q]]);
        eq('without the row’s own ratio nothing is listed as unmeasured', await page.getAttribute('#burst-map', 'data-missing'), '0');
        await page.click('#discover .sc-tab[data-discover="cards"]'); await page.waitForTimeout(150);
        await openAll(page, 'details');
        const r = await readings(page, first.ticker);
        check('the card, the detail line and the scan table print the checklist’s copy', r.card.includes('vol ' + q.toFixed(1) + '×') && r.sub.includes('on ' + q.toFixed(1) + '× volume') && r.table.includes(q.toFixed(1) + '× vol'), [r.card, r.sub, r.table]);
        check('the measurements say the ratio was read from the checklist', r.facts.includes(q.toFixed(1) + '× volume') && r.facts.includes('read from the checklist'), r.facts.slice(0, 300));
        eq('the chart’s burst label carries the checklist’s copy', r.labels, [(Math.round(q * 10) / 10) + '× vol']);
      }
      if (field === 'observations') check('without the observation block the shelf still renders', (await count(page, '#following .ss-following__empty')) === 1 || (await count(page, '#following .ss-followed')) >= 0, 'shelf');
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

// every place the page prints a burst's volume ratio, read back at once
async function readings(page, ticker) {
  return {
    card: (await text(page, `#pick-list .ss-pick[data-ticker="${ticker}"]`)).replace(/\s+/g, ' '),
    sub: await text(page, '#detail .ss-detail__sub'),
    facts: (await text(page, '#disc-checklist')).replace(/\s+/g, ' '),
    table: await text(page, `#burst-${ticker} .sc-signal-matrix__note`),
    labels: await page.locator('#detail .sc-chart--stock text').evaluateAll((els) => els.map((e) => (e.textContent || '').match(/[0-9.]+× vol/)).filter(Boolean).map((m) => m[0]))
  };
}
// a copy of the record with one alteration, served beside the fixtures and removed afterwards
async function openMutant(browser, base, data, mutate, opts) {
  const copy = JSON.parse(JSON.stringify(data)); mutate(copy);
  const p = '/tests/fixtures/page/.mutant.json';
  await writeFile(path.join(ROOT, p), JSON.stringify(copy));
  const opened = await open(browser, base, p, FRESH_NOW, (opts && opts.width) || 1280, Object.assign({ lens: 'all' }, opts));
  return { page: opened.page, errors: opened.errors, close: async () => { await opened.context.close(); await unlink(path.join(ROOT, p)); } };
}
// the volume ratio: zero is a value, an invalid or absent one is missing and said so, and a checklist copy
// that contradicts the row's own field is printed beside it rather than hidden
async function checkVolumeReadings(browser, base, data) {
  console.log('-- the volume ratio readings');
  const first = data.bursts[0], own = first.volume_vs_prior;
  const missingCase = async (name, mutate) => {
    const m = await openMutant(browser, base, data, mutate);
    await m.page.click('#discover .sc-tab[data-discover="map"]'); await m.page.waitForTimeout(250);
    eq(`${name}: the burst is not plotted`, await m.page.getAttribute('#burst-map', 'data-missing'), '1');
    check(`${name}: the burst stays listed and reachable`, (await count(m.page, `#burst-map .ss-map__missing button[data-id="bursts:${first.ticker}"]`)) === 1 && (await text(m.page, '[data-counts]')).includes('1 without a measurement'), await text(m.page, '[data-counts]'));
    await m.page.click(`#burst-map .ss-map__missing button[data-id="bursts:${first.ticker}"]`); await m.page.waitForTimeout(200);
    eq(`${name}: the unplotted burst opens its detail`, await text(m.page, '#detail-h2'), first.ticker);
    await m.page.click('#discover .sc-tab[data-discover="cards"]'); await m.page.waitForTimeout(150);
    await openAll(m.page, 'details');
    const r = await readings(m.page, first.ticker);
    check(`${name}: the card, the detail line and the scan table say the ratio is missing`, r.card.includes('vol —') && r.sub.includes('on —× volume') && r.table.includes('—× vol'), [r.card, r.sub, r.table]);
    check(`${name}: the measurements say the ratio was not recorded`, r.facts.includes('—× volume') && r.facts.includes('volume ratio not recorded'), r.facts.slice(0, 300));
    eq(`${name}: the chart’s burst label carries no ratio`, r.labels, []);
    eq(`${name}: page errors`, m.errors, []);
    await m.close();
  };
  await missingCase('both representations absent', (c) => { c.bursts[0].volume_vs_prior = null; delete c.bursts[0].quality.burst.volume_vs_prior; });
  await missingCase('a negative ratio and a text one', (c) => { c.bursts[0].volume_vs_prior = -1; c.bursts[0].quality.burst.volume_vs_prior = '0.9'; });
  // zero is a value: a session that printed nothing against one that did
  {
    const m = await openMutant(browser, base, data, (c) => { c.bursts[0].volume_vs_prior = 0; c.bursts[0].quality.burst.volume_vs_prior = 0; });
    await m.page.click('#discover .sc-tab[data-discover="map"]'); await m.page.waitForTimeout(250);
    eq('a zero ratio is plotted at zero', await m.page.locator(`#burst-map .ss-map__point[data-ticker="${first.ticker}"]`).evaluateAll((els) => els.map((e) => [+e.dataset.gain, +e.dataset.volume])), [[first.gain_pct, 0]]);
    eq('a zero ratio is not listed as unmeasured', await m.page.getAttribute('#burst-map', 'data-missing'), '0');
    await m.page.click('#discover .sc-tab[data-discover="cards"]'); await m.page.waitForTimeout(150);
    await openAll(m.page, 'details');
    const r = await readings(m.page, first.ticker);
    check('a zero ratio prints as 0.0×, never as missing', r.card.includes('vol 0.0×') && r.sub.includes('on 0.0× volume') && r.table.includes('0.0× vol') && r.facts.includes('0.0× volume') && !r.facts.includes('not recorded') && !r.facts.includes('read from the checklist'), [r.card, r.sub, r.table]);
    eq('the chart’s burst label carries the zero', r.labels, ['0× vol']);
    eq('zero ratio page errors', m.errors, []);
    await m.close();
  }
  // the row's own field stands, and a checklist copy that is not its rounding is printed beside it
  {
    const other = Math.round((own + 0.5) * 100) / 100;
    const m = await openMutant(browser, base, data, (c) => { c.bursts[0].quality.burst.volume_vs_prior = other; });
    await m.page.click('#discover .sc-tab[data-discover="map"]'); await m.page.waitForTimeout(250);
    eq('the row’s own ratio plots the burst, not the checklist’s', await m.page.locator(`#burst-map .ss-map__point[data-ticker="${first.ticker}"]`).evaluateAll((els) => els.map((e) => [+e.dataset.gain, +e.dataset.volume])), [[first.gain_pct, own]]);
    await m.page.click('#discover .sc-tab[data-discover="cards"]'); await m.page.waitForTimeout(150);
    await openAll(m.page, 'details');
    const r = await readings(m.page, first.ticker);
    check('the measurements print the row’s own ratio and the checklist’s disagreeing copy beside it', r.facts.includes(own.toFixed(1) + '× volume') && r.facts.includes('the checklist’s block says ' + other.toFixed(2) + '× volume'), r.facts.slice(0, 300));
    check('the card and the detail line print the row’s own ratio', r.card.includes('vol ' + own.toFixed(1) + '×') && r.sub.includes('on ' + own.toFixed(1) + '× volume'), [r.card, r.sub]);
    eq('disagreeing copy page errors', m.errors, []);
    await m.close();
  }
  // a two-place copy of the row's own four-place ratio is its rounding, not a disagreement
  {
    const m = await openMutant(browser, base, data, (c) => { c.bursts[0].volume_vs_prior = 1.645; c.bursts[0].quality.burst.volume_vs_prior = 1.64; });
    await openAll(m.page, 'details');
    const r = await readings(m.page, first.ticker);
    check('a rounded copy is not called a disagreement', r.facts.includes('1.6× volume') && !r.facts.includes('checklist’s block says'), r.facts.slice(0, 300));
    eq('rounded copy page errors', m.errors, []);
    await m.close();
  }
}

// the volume axis and the tap: a compressed scale that keeps zero, the
// outliers and the recorded values, and a tap resolved by distance rather
// than by which button happened to be appended last
async function checkMapScale(browser, base, data) {
  console.log('-- the volume axis and the crowded tap');
  const mapOpen = async (page) => {
    await page.click('#discover .sc-tab[data-discover="map"]'); await page.waitForTimeout(300);
    await page.locator('#burst-map .ss-map__surface').scrollIntoViewIfNeeded(); await page.waitForTimeout(150);
  };
  const ticks = (page) => page.locator('#burst-map .ss-map__axis[data-tick]').evaluateAll((els) => els.map((e) => [+e.dataset.tick, e.textContent, +e.getAttribute('y')]));
  const dots = (page) => page.locator('#burst-map .ss-map__point').evaluateAll((els) => els.map((e) => {
    const r = e.getBoundingClientRect();
    return { t: e.dataset.ticker, v: +e.dataset.volume, near: +e.dataset.near, cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
  }));

  // ---- the scale, over a record carrying an extreme outlier ----------
  // the published record of 2026-09-11 put one burst at 168.7643x against a
  // median of 1.1x; a linear axis laid 391 of 401 points on the pane floor
  const OUTLIER = 168.7643;
  {
    const m = await openMutant(browser, base, data, (c) => {
      c.bursts[c.bursts.length - 1].volume_vs_prior = OUTLIER;
      c.bursts[c.bursts.length - 1].quality.burst.volume_vs_prior = OUTLIER;
    });
    await mapOpen(m.page);
    const big = data.bursts[data.bursts.length - 1].ticker;
    const t = await ticks(m.page);
    check('every volume tick is labelled with the ratio it stands for', t.length >= 3 && t.every(([v, w]) => w === String(+v.toFixed(2)) + '×'), JSON.stringify(t));
    eq('the axis starts at zero', t[0][0], 0);
    check('the axis top is at or above the largest recorded ratio, so no outlier is clipped', t[t.length - 1][0] >= OUTLIER, JSON.stringify(t[t.length - 1]));
    check('the ticks rise', t.every((x, i) => i === 0 || x[0] > t[i - 1][0]) && t.every((x, i) => i === 0 || x[2] < t[i - 1][2]), JSON.stringify(t.map((x) => x[0])));
    // the compression itself, not the ladder: on a linear axis a 1x tick over a
    // 183x top would sit at 0.5% of the pane, under the floor label. The
    // ladder is uneven either way, so spacing-in-value proves nothing.
    const paneTop = Math.min.apply(null, t.map((x) => x[2])), paneFloor = Math.max.apply(null, t.map((x) => x[2]));
    const one = t.find((x) => x[0] === 1);
    check('a 1× tick sits far above the linear position it would have, because the axis is compressed',
      one && (paneFloor - one[2]) / (paneFloor - paneTop) > 0.15 && 1 / t[t.length - 1][0] < 0.02,
      JSON.stringify({ one: one && one[2], paneTop, paneFloor, top: t[t.length - 1][0] }));
    const d = await dots(m.page);
    const outlier = d.find((x) => x.t === big), rest = d.filter((x) => x.t !== big);
    eq('the outlier is plotted at its own recorded ratio', outlier.v, OUTLIER);
    const floor = Math.max.apply(null, d.map((x) => x.cy));
    check('the rest of the record does not collapse onto the pane floor under the outlier',
      rest.filter((x) => floor - x.cy <= 5).length <= 1, JSON.stringify(rest.map((x) => [x.t, Math.round(floor - x.cy)])));
    check('the outlier still sits above everything else', rest.every((x) => outlier.cy < x.cy), JSON.stringify([outlier, rest[0]]));
    check('the map discloses the compression in words', (await text(m.page, '#burst-map .ss-map__note')).includes('The volume axis is compressed') && (await text(m.page, '#burst-map .ss-map__note')).includes('The gain axis is linear'), await text(m.page, '#burst-map .ss-map__note'));
    eq('outlier page errors', m.errors, []);
    await m.close();
  }
  // ---- zero is a value on the compressed axis, missing is still missing --
  {
    const zero = data.bursts[0].ticker;
    const m = await openMutant(browser, base, data, (c) => {
      c.bursts[0].volume_vs_prior = 0; c.bursts[0].quality.burst.volume_vs_prior = 0;
      c.bursts[c.bursts.length - 1].volume_vs_prior = OUTLIER; c.bursts[c.bursts.length - 1].quality.burst.volume_vs_prior = OUTLIER;
      c.bursts[1].volume_vs_prior = null; delete c.bursts[1].quality.burst.volume_vs_prior;
    });
    await mapOpen(m.page);
    const t = await ticks(m.page), d = await dots(m.page);
    const zeroTickY = t.find((x) => x[0] === 0)[2];
    const zeroDot = d.find((x) => x.t === zero);
    const pane = await m.page.locator('#burst-map .ss-map__surface').boundingBox();
    // the pane floor, read off the vertical grid lines, which the volume
    // scale never touches: comparing the zero point to the zero LABEL would
    // compare it against a value drawn through the same function
    const floorPx = await m.page.locator('#burst-map .ss-map__grid').evaluateAll((els) => {
      const v = els.filter((e) => Math.abs(+e.getAttribute('x1') - +e.getAttribute('x2')) < 0.01);
      return v.length ? Math.max.apply(null, v.map((e) => +e.getAttribute('y2'))) : null;
    });
    eq('a zero ratio is plotted, at zero', zeroDot.v, 0);
    check('a zero ratio sits ON the pane floor', floorPx !== null && Math.abs((zeroDot.cy - pane.y) - floorPx) <= 1.5, JSON.stringify([zeroDot.cy - pane.y, floorPx]));
    check('the 0× label stands beside it', Math.abs((zeroTickY - 4) - floorPx) <= 1.5, JSON.stringify([zeroTickY - 4, floorPx]));
    check('the zero is the lowest point on the pane', d.every((x) => x.cy <= zeroDot.cy), JSON.stringify(d.map((x) => [x.t, Math.round(x.cy)])));
    eq('a missing ratio is still not plotted beside a zero and an outlier', await m.page.getAttribute('#burst-map', 'data-missing'), '1');
    eq('the unmeasured burst is still listed by name', await count(m.page, `#burst-map .ss-map__missing button[data-id="bursts:${data.bursts[1].ticker}"]`), 1);
    eq('zero/missing/outlier page errors', m.errors, []);
    await m.close();
  }
  // ---- a tap where points overlap ------------------------------------
  // two bursts recorded at the same gain and the same ratio share a spot
  // exactly; the browser gives the click to whichever button was appended
  // last, so the page must ask rather than take it
  const A = data.bursts[0].ticker, B = data.bursts[1].ticker;
  const coincide = (c) => {
    c.bursts[1].gain_pct = c.bursts[0].gain_pct;
    c.bursts[1].volume_vs_prior = c.bursts[0].volume_vs_prior;
    if (c.bursts[1].quality && c.bursts[1].quality.burst) c.bursts[1].quality.burst.volume_vs_prior = c.bursts[0].volume_vs_prior;
  };
  for (const [label, width, height, touch] of [['desktop', 1280, 900, false], ['phone', 390, 844, true]]) {
    const copy = JSON.parse(JSON.stringify(data)); coincide(copy);
    const p = '/tests/fixtures/page/.mutant-tap.json';
    await writeFile(path.join(ROOT, p), JSON.stringify(copy));
    const o = await open(browser, base, p, FRESH_NOW, width, { height: height, touch: touch, lens: 'all' });
    const page = o.page;
    // the phone taps with a finger, the desktop clicks with a mouse
    const tap = async (x, y) => { if (touch) await page.touchscreen.tap(x, y); else await page.mouse.click(x, y); };
    await mapOpen(page);
    const d = await dots(page);
    const a = d.find((x) => x.t === A), b = d.find((x) => x.t === B);
    check(`${label}: the two bursts recorded alike share a spot`, Math.abs(a.cx - b.cx) < 1 && Math.abs(a.cy - b.cy) < 1, JSON.stringify([a, b]));
    check(`${label}: each of them counts the other as near`, a.near >= 1 && b.near >= 1, JSON.stringify([a.near, b.near]));
    const before = await page.getAttribute('#burst-map', 'data-selected');
    const topmost = await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); const n = e && e.closest ? e.closest('.ss-map__point') : null; return n ? n.dataset.ticker : null; }, [a.cx, a.cy]);
    await tap(a.cx, a.cy); await page.waitForTimeout(250);
    eq(`${label}: a tap on the shared spot opens the nearby chooser`, await page.getAttribute('#burst-map', 'data-nearby'), 'open');
    eq(`${label}: it chooses nothing on its own`, await page.getAttribute('#burst-map', 'data-selected'), before);
    const listed = await page.locator('.ss-map__nearby-item').evaluateAll((els) => els.map((e) => e.dataset.ticker));
    check(`${label}: both stocks under the finger are offered, not just the topmost`, listed.includes(A) && listed.includes(B), JSON.stringify({ listed, topmost }));
    check(`${label}: the panel says how many are under the finger and that none is chosen`, (await text(page, '.ss-map__nearby h4')).includes('within a finger') && (await text(page, '.ss-map__nearby-hint')).includes('None is chosen'), await text(page, '.ss-map__nearby'));
    eq(`${label}: the first item takes the focus`, await page.evaluate(() => document.activeElement.dataset.ticker), listed[0]);
    // Escape closes it and chooses nothing
    await page.keyboard.press('Escape'); await page.waitForTimeout(150);
    eq(`${label}: Escape closes the chooser without choosing`, [await page.getAttribute('#burst-map', 'data-nearby'), await page.getAttribute('#burst-map', 'data-selected')], ['closed', before]);
    // the stock the finger was on, chosen by name, reaches every view of it
    await tap(a.cx, a.cy); await page.waitForTimeout(250);
    await page.click(`.ss-map__nearby-item[data-ticker="${A}"]`); await page.waitForTimeout(300);
    eq(`${label}: the chosen stock is the one chosen, everywhere`, [
      await hash(page),
      await page.getAttribute('#burst-map', 'data-selected'),
      await page.locator(`#burst-map .ss-map__point[data-ticker="${A}"]`).getAttribute('aria-pressed'),
      await page.locator(`#burst-map .ss-map__table button[data-id="bursts:${A}"]`).getAttribute('aria-pressed'),
      await text(page, '#detail-h2'),
    ], [`#/explore/bursts/${A}`, `bursts:${A}`, 'true', 'true', A]);
    eq(`${label}: the chooser closes once a stock is chosen`, await page.getAttribute('#burst-map', 'data-nearby'), 'closed');
    await page.click('#discover .sc-tab[data-discover="cards"]'); await page.waitForTimeout(200);
    eq(`${label}: the cards carry the same stock`, await page.locator('#pick-list .ss-pick[aria-pressed="true"]').getAttribute('data-ticker'), A);
    // a stock taken from outside the map is the map's selection too: the
    // Choose stock dialog where the layout offers it (a phone), the search
    // where it does not (.ss-choose is display:none above the breakpoint)
    const viaChooser = await page.locator('#choose-open').isVisible();
    if (viaChooser) {
      await page.click('#choose-open'); await page.waitForTimeout(200);
      await page.click(`#chooser-list .ss-chooser__item[data-id="bursts:${B}"]`); await page.waitForTimeout(300);
    } else {
      await page.fill('#search', B.toLowerCase()); await page.press('#search', 'Enter'); await page.waitForTimeout(300);
    }
    await mapOpen(page);
    eq(`${label}: a stock taken from the ${viaChooser ? 'chooser' : 'search'} is the map's selection`, [
      await page.getAttribute('#burst-map', 'data-selected'),
      await page.locator(`#burst-map .ss-map__point[data-ticker="${B}"]`).getAttribute('aria-pressed'),
      await page.locator(`#burst-map .ss-map__table button[data-id="bursts:${B}"]`).getAttribute('aria-pressed'),
      await text(page, '#detail-h2'),
    ], [`bursts:${B}`, 'true', 'true', B]);
    // a point standing alone is chosen by the tap itself, with no chooser
    const alone = (await dots(page)).filter((x) => x.near === 0);
    if (alone.length) {
      await tap(alone[0].cx, alone[0].cy); await page.waitForTimeout(250);
      eq(`${label}: a tap on a point standing alone chooses it outright`, [await page.getAttribute('#burst-map', 'data-nearby'), await page.getAttribute('#burst-map', 'data-selected')], ['closed', 'bursts:' + alone[0].t]);
    } else {
      check(`${label}: a point standing alone exists to tap`, false, 'every point on this fixture is crowded');
    }
    // the keyboard names one point, so Enter takes it and never asks
    await page.locator(`#burst-map .ss-map__point[data-ticker="${A}"]`).focus();
    await page.keyboard.press('Enter'); await page.waitForTimeout(250);
    eq(`${label}: Enter on a focused point chooses that point, with no chooser`, [await page.getAttribute('#burst-map', 'data-nearby'), await page.getAttribute('#burst-map', 'data-selected')], ['closed', 'bursts:' + A]);
    // ...and the crowd is still reachable from the keyboard, beside the selection
    eq(`${label}: a crowded selection offers its nearby list`, await page.locator('.ss-map__nearby-open').isVisible(), true);
    check(`${label}: the selection line counts the crowd`, (await text(page, '#burst-map .ss-map__selection')).includes('within a finger of this point'), await text(page, '#burst-map .ss-map__selection'));
    await page.click('.ss-map__nearby-open'); await page.waitForTimeout(250);
    eq(`${label}: the nearby button opens the chooser`, await page.getAttribute('#burst-map', 'data-nearby'), 'open');
    await page.keyboard.press('ArrowDown');
    const moved = await page.evaluate(() => document.activeElement.dataset.ticker || document.activeElement.className);
    check(`${label}: the arrows move inside the chooser`, moved && moved !== listed[0], String(moved));
    await page.keyboard.press('Enter'); await page.waitForTimeout(300);
    eq(`${label}: Enter in the chooser chooses the focused stock`, await page.getAttribute('#burst-map', 'data-nearby'), 'closed');
    check(`${label}: a stock chosen from the keyboard is one of the two under the finger`, [A, B].includes((await page.getAttribute('#burst-map', 'data-selected') || '').replace('bursts:', '')), await page.getAttribute('#burst-map', 'data-selected'));
    eq(`${label}: tap page errors`, o.errors, []);
    if (shotsDir) await page.locator('#burst-map').screenshot({ path: path.join(shotsDir, `map-nearby-${width}.png`) });
    await o.context.close();
    await unlink(path.join(ROOT, p));
  }
  // the chooser's lifecycle: it is a panel the map owns, so a redraw, an
  // unmount or a route must take it with them, and the keyboard must not
  // escape it or be stranded when it closes
  {
    const copy = JSON.parse(JSON.stringify(data)); coincide(copy);
    const p = '/tests/fixtures/page/.mutant-life.json';
    await writeFile(path.join(ROOT, p), JSON.stringify(copy));
    const o = await open(browser, base, p, FRESH_NOW, 1280, { lens: 'all' });
    const page = o.page;
    const panels = () => count(page, '.ss-map__nearby');
    // the table twin is a disclosure, and the map is rebuilt whenever it is
    // remounted, so it has to be opened again each time it is used
    const openTable = () => openAll(page, '#burst-map .ss-map__table');
    const openIt = async () => {
      await mapOpen(page);
      const b = await page.locator(`#burst-map .ss-map__point[data-ticker="${A}"]`).boundingBox();
      await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2); await page.waitForTimeout(300);
      return page.getAttribute('#burst-map', 'data-nearby');
    };
    eq('the chooser opens on the shared spot', await openIt(), 'open');
    eq('one panel, not two', await panels(), 1);
    eq('opening it again replaces the panel rather than stacking one', [await openIt(), await panels()], ['open', 1]);
    await page.setViewportSize({ width: 900, height: 900 }); await page.waitForTimeout(600);
    eq('a redraw takes the chooser with it', [await panels(), await page.getAttribute('#burst-map', 'data-nearby')], [0, 'closed']);
    await page.setViewportSize({ width: 1280, height: 900 }); await page.waitForTimeout(400);
    await openIt();
    await page.click('#discover .sc-tab[data-discover="cards"]'); await page.waitForTimeout(300);
    eq('unmounting the map leaves no panel behind', await panels(), 0);
    await openIt();
    await go(page, '#/record'); await page.waitForTimeout(300);
    eq('leaving Explore leaves no panel behind', await panels(), 0);
    await go(page, '#/explore/bursts'); await page.waitForTimeout(300);
    // Escape closes it and hands the focus back to a point the reader meant,
    // never to the marker the browser hit-tested: focus on the refused
    // topmost plus one Enter is the silent topmost, one keystroke later.
    // A third stock is selected first, because a selected point is raised
    // (z-index) and would otherwise hit-test as itself.
    const C = data.bursts[2].ticker;
    await mapOpen(page); await openTable();
    await page.click(`#burst-map .ss-map__table button[data-id="bursts:${C}"]`); await page.waitForTimeout(300);
    await openIt();
    eq('the nearest stock takes the focus', await page.evaluate(() => document.activeElement.dataset.ticker), A);
    const box = await page.locator(`#burst-map .ss-map__point[data-ticker="${A}"]`).boundingBox();
    const hit = await page.evaluate(([x, y]) => {
      const e = document.elementFromPoint(x, y), n = e && e.closest ? e.closest('.ss-map__point') : null;
      return n ? n.dataset.ticker : null;
    }, [box.x + box.width / 2, box.y + box.height / 2]);
    check('the browser hit-tests a different stock at that spot', !!hit && hit !== A, String(hit));
    await page.keyboard.press('Escape'); await page.waitForTimeout(250);
    const landed = await page.evaluate(() => document.activeElement.dataset.ticker);
    check('Escape gives the focus back to a point the reader meant, never to the hit-tested marker',
      (await panels()) === 0 && landed !== hit && (landed === C || landed === A), JSON.stringify({ landed, hit, C, A }));
    check('and that marker is not the one the tap resolved to either', hit !== C && hit !== A, String(hit));
    await page.keyboard.press('Enter'); await page.waitForTimeout(300);
    check('Enter after cancelling cannot land on the refused topmost', (await page.getAttribute('#burst-map', 'data-selected')) !== `bursts:${hit}`, await page.getAttribute('#burst-map', 'data-selected'));
    // A selection made anywhere else is a different answer, so a standing
    // panel that describes one tap goes with it. A DEEP LINK is the case that
    // isolates the rule: a click elsewhere also moves the focus out of the
    // panel, and a click that changes the page's height resizes the pane and
    // redraws the map -- either would close the panel whatever update() does,
    // and a mutant that removed the rule survived a table click for exactly
    // that reason. A hash change moves the shared selection and nothing else.
    await go(page, `#/explore/bursts/${B}`); await page.waitForTimeout(300);
    await mapOpen(page);
    await openIt();
    const widthBefore = (await page.locator('#burst-map .ss-map__surface').boundingBox()).width;
    const inPanel = await page.evaluate(() => {
      const q = document.querySelector('.ss-map__nearby');
      return !!q && q.contains(document.activeElement);
    });
    await go(page, `#/explore/bursts/${A}`); await page.waitForTimeout(400);
    const widthAfter = (await page.locator('#burst-map .ss-map__surface').boundingBox()).width;
    check('the focus was inside the panel and the pane did not resize, so only the selection moved',
      inPanel && widthBefore === widthAfter, JSON.stringify([inPanel, widthBefore, widthAfter]));
    eq('a selection that only moves the shared selection closes a standing chooser',
      [await panels(), await page.getAttribute('#burst-map', 'data-selected')], [0, `bursts:${A}`]);
    // and it does not drop the reader on <body>: the panel held the focus, so
    // closing it has to hand the focus somewhere the arrow keys still work
    check('closing it from under the focus keeps the reader on the map', await page.evaluate(() => {
      const a = document.activeElement;
      return !!a && a !== document.body && !!a.closest && !!a.closest('#burst-map');
    }), await page.evaluate(() => document.activeElement ? (document.activeElement.tagName + '/' + document.activeElement.className) : 'none'));
    // and the ordinary ways in close it too
    await openTable();
    await openIt();
    await page.click(`#burst-map .ss-map__table button[data-id="bursts:${B}"]`); await page.waitForTimeout(300);
    eq('a selection from the table closes a standing chooser', [await panels(), await page.getAttribute('#burst-map', 'data-selected')], [0, `bursts:${B}`]);
    await openIt();
    await page.fill('#search', B.toLowerCase()); await page.press('#search', 'Enter'); await page.waitForTimeout(350);
    eq('a selection from the search closes a standing chooser', await panels(), 0);
    await mapOpen(page);
    // it is a popover, not a modal: Tab may leave it, and leaving closes it
    // rather than stranding a panel behind the reader
    await openIt();
    eq('the chooser does not claim a modality the page does not have', await page.getAttribute('.ss-map__nearby', 'aria-modal'), null);
    eq('it is a labelled dialog all the same', [await page.getAttribute('.ss-map__nearby', 'role'), await page.locator('.ss-map__nearby').getAttribute('aria-labelledby')], ['dialog', 'ss-map-nearby-h']);
    for (let i = 0; i < 12; i++) await page.keyboard.press('Tab');
    eq('tabbing out of the chooser closes it', await panels(), 0);
    check('and does not strand the reader on the body', await page.evaluate(() => document.activeElement !== document.body), 'focus');
    // dismissing it by a tap on bare pane keeps the reader's place too
    await openIt();
    const pane = await page.locator('#burst-map .ss-map__surface').boundingBox();
    await page.mouse.click(pane.x + pane.width - 8, pane.y + 8); await page.waitForTimeout(250);
    eq('a tap on bare pane closes it', await panels(), 0);
    check('and the focus is not left on the body', await page.evaluate(() => document.activeElement !== document.body), 'focus');
    eq('lifecycle page errors', o.errors, []);
    await o.context.close();
    await unlink(path.join(ROOT, p));
  }
}

// one fact row's own value, with its <small> note stripped. The plan
// disclosure names several prices in its notes, so a check that searched the
// whole block passed while the ROW under it showed the wrong one: a mutant
// that put the ticket's limit in the day-2 row survived exactly that way.
async function factValue(page, label) {
  const row = page.locator('#disc-plan .sc-facts > div').filter({ has: page.locator('dt', { hasText: new RegExp('^' + label + '$') }) }).first();
  if (!(await row.count())) return null;
  return row.locator('dd').first().evaluate((dd) => { const k = dd.cloneNode(true); k.querySelectorAll('small').forEach((n) => n.remove()); return k.textContent.trim(); });
}

// the four prices a burst ticket keeps apart -- the trigger, the ticket's own
// executable limit, the outer +4% line where day 2 is spent, and the
// indicative entry -- read back off the page, the order sheet, the clipboard
// and the Following snapshot. The fixture carries one of each state.
async function checkTicketPrices(browser, base, data) {
  console.log('-- the ticket limit, the day-2 line and the indicative entry');
  const planned = data.bursts.filter((b) => b.plan);
  const narrowed = planned.find((b) => b.plan.eligible && b.plan.limit < b.plan.day2_spent_above);
  const atCeiling = planned.find((b) => b.plan.eligible && b.plan.limit === b.plan.day2_spent_above);
  const capped = planned.find((b) => b.plan.planned_entry_capped);
  const withheld = planned.find((b) => !b.plan.eligible);
  check('the fixture carries a narrowed ticket, one at the day-2 line, a capped entry and a withheld setup',
        !!(narrowed && atCeiling && capped && withheld),
        [narrowed && narrowed.ticker, atCeiling && atCeiling.ticker, capped && capped.ticker, withheld && withheld.ticker]);
  if (!(narrowed && atCeiling && capped && withheld)) return;
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280);

  for (const b of [narrowed, atCeiling, capped, withheld]) {
    await go(page, `#/explore/bursts/${b.ticker}`);
    await openAll(page, '#detail details');
    const plan = await text(page, '#disc-plan');
    const p = b.plan;
    // each row's OWN value, not merely a price named somewhere in the block
    eq(`${b.ticker}: the buy row's value is the zone up to the ticket limit`, await factValue(page, 'buy'), usd(p.entry_low) + ' – ' + usd(p.limit));
    eq(`${b.ticker}: the skip-above row's value is the day-2 line, not the limit`, await factValue(page, 'skip if it opens above'), usd(p.day2_spent_above));
    eq(`${b.ticker}: the skip-below row's value is the failing line`, await factValue(page, 'skip if it opens below'), usd(p.skip_if_open_below));
    eq(`${b.ticker}: the sized-at row's value is the ticket limit`, await factValue(page, 'sized at'), usd(p.limit));
    check(`${b.ticker}: the buy row still says what the limit is`, plan.includes('limit ' + usd(p.limit)) && plan.includes('day 2 is spent'), plan.slice(0, 600));
    if (p.limit !== p.day2_spent_above) {
      check(`${b.ticker}: the two prices are told apart in words`, plan.includes('the outer threshold and not the ' + usd(p.limit) + ' ticket limit'), plan.slice(0, 800));
      check(`${b.ticker}: the narrowing is disclosed`, plan.includes(p.limit_note), plan.slice(0, 800));
    }
    const refs = await text(page, '#detail [data-refs]').catch(() => '');
    if (refs) {
      check(`${b.ticker}: the levels line names the limit`, refs.includes('limit ' + usd(p.limit)), refs);
      eq(`${b.ticker}: the levels line names the day-2 line only when it differs`, refs.includes('too extended over ' + usd(p.day2_spent_above)), p.limit !== p.day2_spent_above);
    }
    if (p.planned_entry_capped) {
      check(`${b.ticker}: the sized-at row says the indicative entry was capped at the limit`, plan.includes(usd(p.planned_entry) + ' (not a fill; the close +1% would sit over the limit'), plan.slice(0, 900));
      check(`${b.ticker}: the indicative entry equals the limit`, p.planned_entry === p.limit, [p.planned_entry, p.limit]);
    }
    // the entry instruction the decision summary quotes and Following saves:
    // the range's top is the ticket's limit, the SKIP price the day-2 line
    const entry = (b.plan.exit_schedule || []).find((x) => x && x.key === 'entry');
    if (entry) {
      check(`${b.ticker}: the entry instruction buys up to the ticket's limit`, entry.instruction.includes(usd(p.entry_low) + '–' + usd(p.limit)), entry.instruction);
      check(`${b.ticker}: the entry instruction skips at the day-2 line`, entry.instruction.includes('Skip it if it opens above ' + usd(p.day2_spent_above)), entry.instruction);
      if (p.limit !== p.day2_spent_above) check(`${b.ticker}: the entry instruction never calls the limit a skip line`, !entry.instruction.includes('opens above ' + usd(p.limit)), entry.instruction);
    }
    const pre = await text(page, '#detail');
    check(`${b.ticker}: the pre-open check names the +4% line as the extension rule`, pre.includes(usd(p.day2_spent_above) + ' (+4%) day 2 is spent'), pre.slice(0, 600));
    if (p.eligible) check(`${b.ticker}: the pre-open check names the ticket's own limit apart from it`, pre.includes("The ticket's own limit is " + usd(p.limit)), pre.slice(0, 900));
    else check(`${b.ticker}: a withheld setup is told there is no ticket to place`, pre.includes('There is no ticket to place'), pre.slice(0, 900));
  }

  // the order sheet: the limit column is the ticket's, the extension column the day-2 line
  await go(page, '#/explore');
  await openAll(page, 'details');
  const head = await page.locator('#order-sheet thead th').allInnerTexts();
  check('the order sheet names the extension column for the rule, not the action', head.includes('too extended over') && head.includes('limit'), head);
  const iLimit = head.indexOf('limit'), iOuter = head.indexOf('too extended over');
  // the sheet lists only the names the budget left an order with, so it is
  // read for the rows it actually has rather than for every planned burst
  const listed = await page.locator('#order-sheet tbody tr[data-ticker]').evaluateAll((rs) => rs.map((r) => r.dataset.ticker));
  check('the order sheet lists the tickets the record left with an order', listed.length > 0, listed);
  for (const t of listed) {
    const b = planned.find((x) => x.ticker === t);
    const row = page.locator(`#order-sheet tbody tr[data-ticker="${t}"] td`);
    eq(`${t}: the order sheet's limit is the ticket's`, (await row.nth(iLimit - 1).innerText()), usd(b.plan.limit));
    eq(`${t}: the order sheet's extension column is the day-2 line`, (await row.nth(iOuter - 1).innerText()), usd(b.plan.day2_spent_above));
  }
  for (const b of planned.filter((x) => x.plan.order_json)) {
    check(`${b.ticker}: the order's own JSON limit is the ticket's limit`, b.plan.order_json.limit_price === b.plan.limit && b.plan.order_json.stop_price === b.plan.entry_ref && b.plan.order_json.stop_price < b.plan.limit, b.plan.order_json);
  }

  // the clipboard read-back and the Following snapshot carry the same prices
  const trade = planned.find((b) => b.plan.order_json);
  if (trade) {
    await go(page, `#/explore/bursts/${trade.ticker}`);
    await openAll(page, '#detail details');
    const back = await text(page, '#detail pre[data-order]');
    check(`${trade.ticker}: the printed ticket carries the trigger and the ticket limit`, back.includes(usd(trade.plan.entry_ref)) && back.includes(usd(trade.plan.limit)), back);
    check(`${trade.ticker}: the printed ticket never quotes the day-2 line as its limit`, trade.plan.limit === trade.plan.day2_spent_above || !back.includes(usd(trade.plan.day2_spent_above)), back);
    await page.locator('#detail button[data-copy]').first().click();
    const copied = await page.evaluate(() => navigator.clipboard.readText()).catch(() => null);
    if (copied !== null) eq(`${trade.ticker}: the clipboard is the printed ticket`, copied.trim(), back.trim());
    await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
    const card = await text(page, `#following .ss-followed[data-ticker="${trade.ticker}"]`);
    check(`${trade.ticker}: the followed card saves the ticket's limit`, card.includes('limit ' + usd(trade.plan.limit)), card);
    eq(`${trade.ticker}: the followed card names the day-2 line only when it differs`, card.includes('too extended over ' + usd(trade.plan.day2_spent_above)), trade.plan.limit !== trade.plan.day2_spent_above);
  }

  // a record from before the split carries no day-2 field: nothing invents one
  const older = await openMutant(browser, base, data, (c) => c.bursts.forEach((b) => { if (b.plan) delete b.plan.day2_spent_above; }));
  await go(older.page, `#/explore/bursts/${narrowed.ticker}`);
  await openAll(older.page, '#detail details');
  const shown = await text(older.page, '#detail');
  check('without the day-2 field the page prints no invented price', !shown.includes('too extended over'), shown.slice(0, 400));
  eq('without the day-2 field the page still renders', await text(older.page, '#detail-h2'), narrowed.ticker);
  eq('without the day-2 field: page errors', older.errors, []);
  await older.close();

  eq('the ticket-price journey: page errors', errors, []);
  await context.close();
}


// ---------------------------------------------------------------- the lenses
// Every subset below is worked out from the RECORD and compared with what the
// page draws -- never with the page's own count. The map is read back for the
// same population, because the defect worth catching is cards and map quietly
// showing two different sets. And a lens is a reading of the record, never a
// permission: a page that offers no order still offers none with "with
// ticket" in force.
async function checkLens(browser, base, data) {
  console.log('-- the discovery lenses');
  const ticketed = data.bursts.filter((b) => burstStatus(b, data) === 'ticket').map((b) => b.ticker);
  const aQuality = data.bursts.filter((b) => TRADE_GRADES.includes(b.grade)).map((b) => b.ticker);
  const all = data.bursts.map((b) => b.ticker);
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280);

  eq('the lens row offers A-quality, all, with ticket and following', await page.locator('#lens .sc-tab[data-lens]').evaluateAll((e) => e.map((x) => x.dataset.lens)), ['a', 'all', 'ticket', 'following']);
  eq('each lens wears the count it will show', await page.locator('#lens .sc-tab[data-lens]').evaluateAll((e) => e.map((x) => [x.dataset.lens, +x.dataset.count])),
    [['a', aQuality.length], ['all', all.length], ['ticket', ticketed.length], ['following', 0]]);
  eq('the A-quality lens shows the archived A and A+ grades', await cardTickers(page), aQuality);
  eq('the heading keeps the stage total beside the subset', await text(page, '#picks-h2'), `bursts · ${aQuality.length} of ${all.length}`);
  await setLens(page, 'ticket');
  eq('the ticket lens shows the stocks the record wrote a ticket for', await cardTickers(page), ticketed);
  await setLens(page, 'all');
  eq('the all lens shows every burst', await cardTickers(page), all);
  // the map is the cards' twin: the same names, and a count that reconciles
  await setLens(page, 'a');
  await page.click('#discover .sc-tab[data-discover="map"]'); await page.waitForTimeout(350);
  eq('the map plots the lens\'s own subset', await page.locator('#burst-map .ss-map__point').evaluateAll((e) => e.map((x) => x.dataset.ticker)), aQuality);
  eq('the map\'s table twin lists the same subset', await count(page, '#burst-map .ss-map__table tbody tr'), aQuality.length);
  check('the map reconciles its subset with the stage total and names the lens',
    (await text(page, '#burst-map [data-counts]')).includes(`${aQuality.length} bursts of ${all.length} · A-quality lens`), await text(page, '#burst-map [data-counts]'));
  await setLens(page, 'all');
  await page.waitForTimeout(250);
  eq('widening the lens widens the map with it', await count(page, '#burst-map .ss-map__point'), all.length);
  check('an unnarrowed map says nothing about a lens', !(await text(page, '#burst-map [data-counts]')).includes('lens'), await text(page, '#burst-map [data-counts]'));
  await page.click('#discover .sc-tab[data-discover="cards"]'); await page.waitForTimeout(200);

  // the stepper walks the same list, and the published rank stays a label
  await setLens(page, 'a');
  eq('the stepper counts the visible list', await text(page, '#detail [data-where]'), `1 of ${aQuality.length}`);
  await page.click('#detail .ss-step[data-step="next"]'); await page.waitForTimeout(200);
  eq('next steps inside the lens', [await text(page, '#detail-h2'), await text(page, '#detail [data-where]')], [aQuality[1], `2 of ${aQuality.length}`]);
  eq('the cards carry the published rank whatever the lens', await page.locator('#pick-list .ss-pick').evaluateAll((e) => e.map((x) => +x.dataset.rank)), aQuality.map((t) => data.bursts.findIndex((b) => b.ticker === t) + 1));

  // sorting is presentation: the order changes, the rank label does not
  await setLens(page, 'all');
  await page.click('#lens .sc-tab[data-sort="gain"]'); await page.waitForTimeout(250);
  const byGain = data.bursts.slice().sort((x, y) => (y.gain_pct - x.gain_pct) || (data.bursts.indexOf(x) - data.bursts.indexOf(y))).map((b) => b.ticker);
  eq('sorting by gain reorders the cards by the recorded gain', await cardTickers(page), byGain);
  eq('sorting leaves every published rank where the run put it', await page.locator('#pick-list .ss-pick').evaluateAll((e) => e.map((x) => [x.dataset.ticker, +x.dataset.rank])), byGain.map((t) => [t, data.bursts.findIndex((b) => b.ticker === t) + 1]));
  check('the status line says what it is sorted by', (await text(page, '#picks-status')).includes('sorted by the session’s gain'), await text(page, '#picks-status'));
  await page.click('#lens .sc-tab[data-sort="rank"]'); await page.waitForTimeout(200);
  eq('rank restores the run\'s own order', await cardTickers(page), all);

  // reset: one action back to the record's own lens, order and search
  await setLens(page, 'ticket');
  await page.fill('#search', 'A'); await page.waitForTimeout(200);
  eq('the reset appears once a filter is in force', await count(page, '#lens [data-reset]'), 1);
  await page.click('#lens [data-reset]'); await page.waitForTimeout(250);
  eq('reset returns to the lens the record earns, with the search cleared', [await lensNow(page), await page.inputValue('#search')], [openingLens(data), '']);
  eq('reset leaves no reset to press', await count(page, '#lens [data-reset]'), 0);

  // an exact ticker the lens hides is explained and offered, never denied
  const hidden = data.bursts.find((b) => !TRADE_GRADES.includes(b.grade));
  await page.fill('#search', hidden.ticker); await page.waitForTimeout(250);
  eq('a stock behind the lens is not called missing', await count(page, '#pick-list [data-empty="lens-hidden"]'), 1);
  const hiddenBox = await text(page, '#pick-list [data-empty="lens-hidden"]');
  check('it says which lens is hiding it and what it is graded', hiddenBox.includes('hidden by the A-quality lens') && hiddenBox.includes('graded ' + hidden.grade), hiddenBox);
  await page.click('#pick-list [data-lens-out]'); await page.waitForTimeout(300);
  eq('one action inspects it', [await text(page, '#detail-h2'), await hash(page)], [hidden.ticker, `#/explore/bursts/${hidden.ticker}`]);
  check('and the page says the lens was widened for it', (await text(page, '#picks-status')).includes('outside the A-quality lens'), await text(page, '#picks-status'));
  eq('lens page errors', errors, []);
  await context.close();

  // Every A-quality burst in the fixtures happens to be A+, so a lens that read
  // A+ ALONE would pass every check above. The lens reads the record's OWN
  // trade grades, so a plain A belongs in it too.
  const plainA = await openMutant(browser, base, data, (c) => { c.bursts[0].grade = 'A'; }, { lens: 'a' });
  check('the A-quality lens is the record’s own trade grades, not A+ alone',
    (await cardTickers(plainA.page)).includes(data.bursts[0].ticker), await cardTickers(plainA.page));
  eq('plain-A lens page errors', plainA.errors, []);
  await plainA.close();

  // a bookmark that NAMES a stock the stored lens hides is a request to inspect
  // it: the lens widens on that load, says so, and is not written to storage
  const deep = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'a', hash: `#/explore/bursts/${hidden.ticker}` });
  eq('a bookmarked stock behind the lens still opens', await text(deep.page, '#detail-h2'), hidden.ticker);
  check('and the page says which lens it widened', (await text(deep.page, '#picks-status')).includes('outside the A-quality lens'), await text(deep.page, '#picks-status'));
  await deep.page.goto(await deep.page.url().replace(/#.*$/, ''), { waitUntil: 'load' });
  await deep.page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
  await deep.page.waitForTimeout(400);
  eq('the widening was never stored: a plain visit is A-quality again', await lensNow(deep.page), 'a');
  eq('deep-link lens page errors', deep.errors, []);
  await deep.context.close();

  // the Following lens: this browser's shelf, and nothing else
  const f = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { hash: `#/explore/bursts/${aQuality[1]}` });
  eq('following is empty before anything is followed', await f.page.locator('#lens .sc-tab[data-lens="following"]').getAttribute('data-count'), '0');
  await f.page.click('#detail .ss-follow button[data-follow-action="add"]'); await f.page.waitForTimeout(250);
  eq('following counts the setup just saved', await f.page.locator('#lens .sc-tab[data-lens="following"]').getAttribute('data-count'), '1');
  await setLens(f.page, 'following');
  eq('the following lens shows exactly what this browser saved', await cardTickers(f.page), [aQuality[1]]);
  await f.page.click('#detail .ss-follow button[data-follow-action="remove"]'); await f.page.waitForTimeout(300);
  // the reader's own action emptied the lens: the page must stay in it and say
  // so, not step out to every burst because the hash still names the stock
  eq('unfollowing empties the lens and stays in it', [await lensNow(f.page), await count(f.page, '#pick-list [data-empty="lens"]')], ['following', 1]);
  check('the empty following lens explains itself', (await text(f.page, '#pick-list [data-empty="lens"]')).includes('Following shelf'), await text(f.page, '#pick-list [data-empty="lens"]'));
  await f.page.click('#pick-list [data-lens-out]'); await f.page.waitForTimeout(250);
  eq('one action recovers it', await cardTickers(f.page), all);
  eq('following lens page errors', f.errors, []);
  await f.context.close();

  // A saved signal belongs to the night it was saved on. The next night's
  // record carries the same symbol under a DIFFERENT identity, so the shelf
  // keeps the old one, the lens does not count it as a candidate of tonight's
  // record, and tonight's signal is offered on its own terms -- never a silent
  // substitution of one signal for another.
  {
    const t = data.bursts[0].ticker;
    const o = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${t}` });
    await o.page.click('#detail .ss-follow button[data-follow-action="add"]'); await o.page.waitForTimeout(250);
    const saved = await o.page.evaluate(() => window.SCStock.follow.list().map((i) => [i.ticker, i.session]));
    eq(`${t} is saved under the session it was signalled on`, saved, [[t, data.run.session]]);
    const next = '2026-09-11';
    const copy = JSON.parse(JSON.stringify(data));
    copy.run.session = next; copy.run.expected_session = next;
    copy.bursts.forEach((b) => { if ((b.series || []).length) b.series[b.series.length - 1].date = next; });
    const p2 = '/tests/fixtures/page/.mutant-night.json';
    await writeFile(path.join(ROOT, p2), JSON.stringify(copy));
    // the next night in the same browser: a later init script wins, and the
    // query makes it a real navigation (a goto that moves only the fragment is
    // a same-document one, and nothing re-runs)
    await o.page.addInitScript((u) => { window.SCStock = { dataUrl: u, now: '2026-09-11T22:31:00Z' }; }, p2);
    await o.page.goto(base + `/docs/index.html?night=2#/explore/bursts/${t}`, { waitUntil: 'load' });
    await o.page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
    await o.page.waitForTimeout(400);
    eq('the page is on the next night', await o.page.evaluate(() => window.SCStock.data.run.session), next);
    eq('the older saved signal is kept, not replaced by tonight’s', await o.page.evaluate(() => window.SCStock.follow.list().map((i) => [i.ticker, i.session])), [[t, data.run.session]]);
    eq('and it is not counted among tonight’s candidates', await o.page.locator('#lens .sc-tab[data-lens="following"]').getAttribute('data-count'), '0');
    eq('tonight’s signal for the same symbol is offered on its own terms', await count(o.page, '#detail .ss-follow button[data-follow-action="add"]'), 1);
    eq('while the shelf still carries the older one', await count(o.page, `#following .ss-followed[data-ticker="${t}"]`), 1);
    eq('two-night follow page errors', o.errors, []);
    await o.context.close();
    await unlink(path.join(ROOT, p2));
  }

  // a lens the reader chose survives a reload, empty or not: nothing is widened behind their back
  const red = JSON.parse(await readFile(path.join(FIXTURES, 'red.json'), 'utf8'));
  const r1 = await open(browser, base, '/tests/fixtures/page/red.json', FRESH_NOW, 1280);
  eq('a red record still opens on its A-quality research', [await lensNow(r1.page), (await cardTickers(r1.page)).length], ['a', red.bursts.filter((b) => TRADE_GRADES.includes(b.grade)).length]);
  eq('and offers no order anywhere on it', [await count(r1.page, '#detail pre[data-order]'), await count(r1.page, '#order-sheet tbody tr[data-ticker]')], [0, 0]);
  eq('no card on it claims a ticket', await count(r1.page, '#pick-list .ss-pick[data-status="ticket"]'), 0);
  await setLens(r1.page, 'ticket');
  eq('the ticket lens on a red night is empty and says so', await count(r1.page, '#pick-list [data-empty="lens"]'), 1);
  check('and names breadth as the reason', (await text(r1.page, '#pick-list [data-empty="lens"]')).includes('breadth is red'), await text(r1.page, '#pick-list [data-empty="lens"]'));
  await r1.page.reload({ waitUntil: 'load' }); await r1.page.waitForTimeout(600);
  eq('a reload does not silently widen an empty lens', [await lensNow(r1.page), await count(r1.page, '#pick-list [data-empty="lens"]')], ['ticket', 1]);
  eq('red lens page errors', r1.errors, []);
  await r1.context.close();

  // a record with no A-quality burst opens on every burst rather than on nothing
  const nt = JSON.parse(await readFile(path.join(FIXTURES, 'notrade.json'), 'utf8'));
  const n1 = await open(browser, base, '/tests/fixtures/page/notrade.json', FRESH_NOW, 1280);
  eq('without an A grade the first visit shows every burst', [await lensNow(n1.page), (await cardTickers(n1.page)).length], ['all', nt.bursts.length]);
  eq('and the A-quality lens says it would show none', await n1.page.locator('#lens .sc-tab[data-lens="a"]').getAttribute('data-count'), '0');
  eq('no-A page errors', n1.errors, []);
  await n1.context.close();

  // THE SAFETY GATE: a page that offers no order offers none through a lens
  const stale = await open(browser, base, '/tests/fixtures/page/full.json', STALE1_NOW, 1280, { lens: 'ticket' });
  eq('a stale page still shows the record\'s ticketed stock', await cardTickers(stale.page), ticketed);
  eq('but writes no order for it', [await count(stale.page, '#detail pre[data-order]'), await count(stale.page, '#order-sheet tbody tr[data-ticker]')], [0, 0]);
  eq('and the action area says it is not offered', await stale.page.locator('#detail .ss-action').getAttribute('data-ticket'), 'blocked');
  check('the lens says the ticket is the record\'s, not an offer', (await text(stale.page, '#picks-status')).includes('as the record wrote them'), await text(stale.page, '#picks-status'));
  eq('stale lens page errors', stale.errors, []);
  await stale.context.close();

  // A missing measurement sorts last and is never read as a zero. Every gain in
  // the fixtures -- and every one of the 401 in the published record, the
  // smallest +0.07% -- is positive, so a missing GAIN read as zero would still
  // sort last and prove nothing. The volume ratio is the discriminating case:
  // zero is a value the record writes, so a burst measured at 0x must outrank
  // one that was not measured at all, and reading missing as zero ties them.
  const zeroT = data.bursts[1].ticker, noneT = data.bursts[0].ticker;
  const nog = await openMutant(browser, base, data, (c) => {
    c.bursts[0].volume_vs_prior = null; delete c.bursts[0].quality.burst.volume_vs_prior;
    c.bursts[1].volume_vs_prior = 0; c.bursts[1].quality.burst.volume_vs_prior = 0;
  }, { sort: 'volume' });
  const order = await cardTickers(nog.page);
  eq('a burst with no volume measurement sorts last', order[order.length - 1], noneT);
  eq('and one the record measured at zero still outranks it', order[order.length - 2], zeroT);
  check('the unmeasured card says so', (await text(nog.page, `#pick-list .ss-pick[data-ticker="${noneT}"]`)).includes('vol —'), await text(nog.page, `#pick-list .ss-pick[data-ticker="${noneT}"]`));
  check('and the zero card prints the zero', (await text(nog.page, `#pick-list .ss-pick[data-ticker="${zeroT}"]`)).includes('vol 0.0×'), await text(nog.page, `#pick-list .ss-pick[data-ticker="${zeroT}"]`));
  eq('missing-measure sort page errors', nog.errors, []);
  await nog.close();
}

// ---------------------------------------------------------------- comparison
// Two charts on one page is the thing that used to be impossible: one global
// host, fixed ids, and a second mount disposing the first. So this reads back
// both instances, their ids, and the live-chart count the module keeps.
async function checkCompare(browser, base, data) {
  console.log('-- comparing two setups');
  const live = (page) => page.evaluate(() => window.SCStock.liveCharts());
  const ids = (page) => page.evaluate(() => Array.from(document.querySelectorAll('[id]')).map((e) => e.id));
  const A = data.bursts[0], B = data.bursts[1];
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all' });

  eq('every card offers a Compare toggle beside its selection button', await count(page, '#pick-list .ss-pick-item .ss-pin'), data.bursts.length);
  eq('the toggle is never inside the selection button', await count(page, '#pick-list .ss-pick .ss-pin'), 0);
  eq('the tray is out of the way until something is pinned', await page.locator('#compare-tray').isVisible(), false);
  const before = await hash(page);
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await page.waitForTimeout(200);
  eq('pinning navigates nowhere', await hash(page), before);
  eq('pinning follows nothing', await page.evaluate(() => (window.SCStock.follow.list() || []).length), 0);
  check('one pin asks for a second and offers no comparison yet', (await text(page, '#compare-tray')).includes('pin one more') && await page.locator('#compare-open').isDisabled(), await text(page, '#compare-tray'));
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`); await page.waitForTimeout(200);
  eq('two pins enable the comparison', await page.locator('#compare-open').isDisabled(), false);
  eq('the tray names both, with the stage and the status the record gives them', await page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [B.ticker, A.ticker]);

  // a third asks; it never drops one silently
  const C = data.bursts[2];
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${C.ticker}"]) .ss-pin`); await page.waitForTimeout(200);
  eq('a third pin asks which to replace', await page.locator('#compare-tray .ss-tray__ask').getAttribute('data-ask'), 'replace');
  eq('and offers each of the two by name', await page.locator('#compare-tray [data-ask-action="replace"]').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [B.ticker, A.ticker]);
  eq('until it is answered the pair is untouched', await page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [B.ticker, A.ticker]);
  await page.click('#compare-tray [data-ask-action="cancel"]'); await page.waitForTimeout(150);
  eq('keeping the pair keeps the pair', [await count(page, '#compare-tray .ss-tray__ask'), await page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker))], [0, [B.ticker, A.ticker]]);
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${C.ticker}"]) .ss-pin`); await page.waitForTimeout(150);
  await page.click(`#compare-tray [data-ask-action="replace"][data-ticker="${B.ticker}"]`); await page.waitForTimeout(200);
  eq('replacing swaps exactly the one named', await page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [C.ticker, A.ticker]);

  // the other stage is explained, not silently refused
  const coil = data.watchlist.top[0];
  await page.locator('#stages .ss-stage[data-stage="setting-up"]').click(); await page.waitForTimeout(250);
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${coil.ticker}"]) .ss-pin`); await page.waitForTimeout(200);
  eq('a pin from the other stage is explained', await page.locator('#compare-tray .ss-tray__ask').getAttribute('data-ask'), 'stage');
  check('and says why the two are not put side by side', (await text(page, '#compare-tray .ss-tray__ask')).includes('one stage and one published session'), await text(page, '#compare-tray .ss-tray__ask'));
  await page.click('#compare-tray [data-ask-action="restart"]'); await page.waitForTimeout(200);
  eq('starting again keeps only the new one', await page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [coil.ticker]);
  await page.click('#compare-tray [data-tray-clear]'); await page.waitForTimeout(150);
  eq('clearing puts the tray away', await page.locator('#compare-tray').isVisible(), false);

  // two charts, side by side, each its own instance
  await page.locator('#stages .ss-stage[data-stage="bursts"]').click(); await page.waitForTimeout(250);
  const one = await live(page);
  eq('one chart is live before the sheet opens', one, 1);
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await page.waitForTimeout(200);
  const routeBefore = await hash(page), lensBefore = await lensNow(page);
  await page.click('#compare-open'); await page.waitForTimeout(700);
  eq('the sheet opens', await page.evaluate(() => document.getElementById('compare').open), true);
  eq('two charts are drawn and neither disposed the other', [await count(page, '#compare .sc-chart--stock'), await live(page)], [2, 3]);
  eq('each panel owns its own mount id', await page.locator('#compare .ss-chart-mount').evaluateAll((e) => e.map((x) => x.id)), ['cmp-a-mount', 'cmp-b-mount']);
  const allIds = await ids(page);
  eq('no id is written twice while both charts stand', allIds.length, new Set(allIds).size);
  eq('each chart is its own stock', await page.locator('#compare .sc-chart--stock').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [A.ticker, B.ticker]);
  // each keeps its own price scale and its own dates: the two are never on one axis
  const scales = await page.locator('#compare .sc-chart--stock').evaluateAll((els) => els.map((h) => ({
    ticker: h.dataset.ticker, sessions: h.dataset.sessions,
    gutter: Array.from(h.querySelectorAll('svg text[data-kind]')).map((t) => t.textContent).join('|')
  })));
  check('each panel keeps its own price labels', scales.length === 2 && scales[0].gutter && scales[1].gutter && scales[0].gutter !== scales[1].gutter, JSON.stringify(scales));
  const ranges = await page.locator('#compare .ss-chart-panel__range').allInnerTexts();
  check('each panel labels its own actual range', ranges.length === 2 && ranges.every((r) => /^Showing \d+ sessions, .+ – .+ \d{4} · /.test(r.replace(/\s+/g, ' '))), JSON.stringify(ranges));
  // the common controls drive both, and the per-panel strips stay out of the way
  eq('the per-panel control strips are hidden under the common ones', await page.locator('#compare .ss-chart-panel__tools').evaluateAll((e) => e.map((x) => x.hidden)), [true, true]);
  await page.click('#compare .ss-compare__tools .sc-tab[data-mode="candles"]'); await page.waitForTimeout(400);
  eq('one mode choice redraws both charts', await page.locator('#compare .sc-chart--stock').evaluateAll((e) => e.map((x) => x.dataset.mode)), ['candles', 'candles']);
  await page.click('#compare .ss-compare__tools .sc-tab[data-range="120"]'); await page.waitForTimeout(400);
  eq('one range choice redraws both charts', await page.locator('#compare .sc-chart--stock').evaluateAll((e) => e.map((x) => x.dataset.range)), ['120', '120']);
  eq('and both are still live', await live(page), 3);
  // the facts: the record's own values, aligned, with no winner declared
  const facts = await page.locator('#compare-table tbody tr').evaluateAll((rows) => rows.map((r) => [r.dataset.fact, r.dataset.differs, r.children[1].textContent.trim(), r.children[2].textContent.trim()]));
  // the rows exist in the DOM either way: what matters is that the sheet gives
  // them the height they need (a scrolling column flex box shrinks its items)
  const factsBox = await page.evaluate(() => { const b = document.querySelector('#compare .ss-compare__facts'), t = document.getElementById('compare-table');
    return { drawn: Math.round(b.getBoundingClientRect().height), content: t.scrollHeight }; });
  check('the aligned facts are drawn at the height their rows need', factsBox.drawn >= factsBox.content - 2, JSON.stringify(factsBox));
  const fact = (k) => facts.find((f) => f[0] === k);
  eq(`${A.ticker}: the compared grade is the archived one`, fact('grade')[2], A.grade + ' · ' + A.score.toFixed(1));
  eq(`${B.ticker}: the compared grade is the archived one`, fact('grade')[3], B.grade + ' · ' + B.score.toFixed(1));
  eq('the compared gains are the recorded gains', [fact('gain')[2], fact('gain')[3]], [pctOf(A.gain_pct), pctOf(B.gain_pct)]);
  eq('the volume row names which ratio it is', await page.locator('#compare-table tr[data-fact="volume"] th').innerText(), 'volume vs previous session');
  eq('the compared volume ratios are the recorded ones', [fact('volume')[2], fact('volume')[3]], [ratioOf(A).toFixed(1) + '×', ratioOf(B).toFixed(1) + '×']);
  if (A.plan) eq(`${A.ticker}: the compared trigger is the plan's`, fact('trigger')[2], usd(A.plan.entry_ref));
  if (A.plan) eq(`${A.ticker}: the compared limit is the ticket's`, fact('limit')[2], usd(A.plan.limit));
  if (B.plan) eq(`${B.ticker}: the compared limit is the ticket's`, fact('limit')[3], usd(B.plan.limit));
  check('a row the two differ on is marked, one they share is not', fact('gain')[1] === 'true' && fact('provenance')[1] === 'false', JSON.stringify(facts.map((f) => [f[0], f[1]])));
  // the table's own caption and the sheet's footnote exist to DENY a verdict,
  // so the rows, the column heads and the panels are read without them
  const compared = (await page.locator('#compare-table thead, #compare-table tbody').allInnerTexts()).join(' ') + ' ' + (await text(page, '#compare .ss-compare__panels'));
  check('nothing in the comparison itself declares a winner', !/\b(winner|better|best|stronger|weaker|beats|wins|leads)\b/i.test(compared), (compared.match(/.{0,60}(winner|better|best|stronger|weaker|beats|wins|leads)/i) || [''])[0]);
  eq('no row is marked as the one to take', await count(page, '#compare-table [data-best], #compare-table .is-best'), 0);
  check('and the caption says the mark is a difference, not a verdict', (await text(page, '#compare')).includes('nothing here says which setup is better'), 'caption');
  if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'compare-1280.png') });

  // closing: both instances dropped, the reader's place restored
  const scrollBefore = await page.evaluate(() => window.pageYOffset);
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  eq('Escape closes the sheet', await page.evaluate(() => document.getElementById('compare').open), false);
  eq('both comparison charts are disposed', await live(page), 1);
  eq('nothing of the sheet is left in the page', await count(page, '#compare .sc-chart--stock'), 0);
  eq('focus returns to what opened it', await page.evaluate(() => (document.activeElement || {}).id || ''), 'compare-open');
  eq('the reader keeps their place', await page.evaluate(() => window.pageYOffset), scrollBefore);
  eq('the selection and the lens are untouched', [await hash(page), await lensNow(page)], [routeBefore, lensBefore]);
  // opening and closing repeatedly leaks nothing and shows no stale content
  for (let i = 0; i < 3; i++) {
    await page.click('#compare-open'); await page.waitForTimeout(450);
    eq(`open ${i + 1}: two charts, three live`, [await count(page, '#compare .sc-chart--stock'), await live(page)], [2, 3]);
    const again = await ids(page);
    eq(`open ${i + 1}: still no duplicated id`, again.length, new Set(again).size);
    await page.keyboard.press('Escape'); await page.waitForTimeout(400);
    eq(`close ${i + 1}: back to one live chart`, await live(page), 1);
  }
  // a replaced pin shows the new pair, not the old one
  await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${C.ticker}"]) .ss-pin`); await page.waitForTimeout(150);
  await page.click(`#compare-tray [data-ask-action="replace"][data-ticker="${A.ticker}"]`); await page.waitForTimeout(200);
  await page.click('#compare-open'); await page.waitForTimeout(500);
  eq('the sheet shows the pair now pinned', await page.locator('#compare .sc-chart--stock').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [C.ticker, B.ticker]);
  // Open setup leaves the sheet for that stock
  await page.click(`#compare [data-open-setup="${C.ticker}"]`); await page.waitForTimeout(500);
  eq('Open setup closes the sheet and opens that stock', [await page.evaluate(() => document.getElementById('compare').open), await text(page, '#detail-h2')], [false, C.ticker]);
  eq('and leaves one chart live', await live(page), 1);
  eq('compare page errors', errors, []);
  await context.close();

  // following from the comparison is the one save there is, and the record is untouched
  const fl = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all' });
  await fl.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
  await fl.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await fl.page.waitForTimeout(200);
  await fl.page.click('#compare-open'); await fl.page.waitForTimeout(500);
  await fl.page.click('#compare [data-side="a"] .ss-follow button[data-follow-action="add"]'); await fl.page.waitForTimeout(250);
  eq('following from the comparison saves one setup in this browser', await fl.page.evaluate(() => window.SCStock.follow.list().map((i) => i.ticker)), [A.ticker]);
  eq('and the published record is not touched by it', await fl.page.evaluate(() => JSON.stringify(window.SCStock.data.trades) + '|' + JSON.stringify(window.SCStock.data.scorecard)),
    JSON.stringify(data.trades) + '|' + JSON.stringify(data.scorecard));
  eq('comparison follow page errors', fl.errors, []);
  await fl.context.close();

  // Two balanced panels: a long company name on one side must not push its
  // chart below the other's. The fixture's names are short, so the case is
  // made rather than hoped for -- the published record's are not short.
  const longName = await openMutant(browser, base, data, (c) => { c.bursts[0].name = 'A Very Long Company Name Corporation Of America Incorporated Holdings International Group Common Stock Class A Ordinary Shares'; }, { lens: 'all' });
  await longName.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
  await longName.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await longName.page.waitForTimeout(200);
  await longName.page.click('#compare-open'); await longName.page.waitForTimeout(600);
  const tops = await longName.page.locator('#compare .ss-compare__side .ss-chart-panel').evaluateAll((e) => e.map((x) => Math.round(x.getBoundingClientRect().top)));
  check('the two panels start their charts at the same height', tops.length === 2 && Math.abs(tops[0] - tops[1]) <= 1, tops);
  const names = await longName.page.locator('#compare .ss-compare__side .ss-compare__name').evaluateAll((e) => e.map((x) => Math.round(x.getBoundingClientRect().height)));
  check('and neither identity block grew a second line', names.length === 2 && Math.abs(names[0] - names[1]) <= 1, names);
  eq('long-name comparison page errors', longName.errors, []);
  await longName.close();

  // a side with no archived bars is the designed absence, and the other still draws
  const nb = await openMutant(browser, base, data, (c) => { c.bursts[1].series = []; }, { lens: 'all' });
  await nb.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
  await nb.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await nb.page.waitForTimeout(200);
  await nb.page.click('#compare-open'); await nb.page.waitForTimeout(500);
  eq('the side without bars says so rather than inventing a chart', [await count(nb.page, '#compare [data-side="b"] [data-chart="unavailable"]'), await count(nb.page, '#compare [data-side="b"] .sc-chart--stock')], [1, 0]);
  eq('and the side with bars still draws', await count(nb.page, '#compare [data-side="a"] .sc-chart--stock'), 1);
  check('the facts still compare what the record does carry', (await text(nb.page, '#compare-table')).includes(B.ticker), 'facts');
  eq('no-bars comparison page errors', nb.errors, []);
  await nb.close();

  // the phone: one chart at a time, both symbols and both statuses on screen
  const m = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844, lens: 'all' });
  await m.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
  await m.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await m.page.waitForTimeout(200);
  await m.page.click('#compare-open'); await m.page.waitForTimeout(700);
  eq('phone: the A/B switch is offered', await m.page.locator('#compare .ss-compare__ab').isVisible(), true);
  const visibleCharts = () => m.page.locator('#compare .ss-chart-panel').evaluateAll((e) => e.filter((x) => x.getClientRects().length).length);
  eq('phone: one chart is drawn at a time', await visibleCharts(), 1);
  const bothIds = await m.page.locator('#compare .ss-compare__both .ss-compare__id').evaluateAll((e) => e.map((x) => [x.dataset.idOf, x.getClientRects().length > 0]));
  eq('phone: both symbols and both statuses stay on screen', bothIds, [[A.ticker, true], [B.ticker, true]]);
  const bothBox = await m.page.locator('#compare .ss-compare__both').boundingBox();
  check('phone: both identities are above the fold', bothBox && bothBox.y + bothBox.height <= 844, JSON.stringify(bothBox));
  await m.page.click('#compare .ss-compare__ab .sc-tab[data-ab="b"]'); await m.page.waitForTimeout(500);
  eq('phone: the switch changes which chart is drawn', await m.page.locator('#compare .ss-chart-panel').evaluateAll((e) => e.map((x) => [x.dataset.ticker, x.getClientRects().length > 0])), [[A.ticker, false], [B.ticker, true]]);
  check('phone: the revealed chart is measured for the screen it is on', await m.page.evaluate(() => { const s = document.querySelector('#compare [data-side="b"] svg'); return s && +s.getAttribute('width') <= 390; }), 'width');
  eq('phone: the aligned facts are still there', await count(m.page, '#compare-table tbody tr'), facts.length);
  const mBox = await m.page.evaluate(() => { const b = document.querySelector('#compare .ss-compare__facts'), t = document.getElementById('compare-table');
    return { drawn: Math.round(b.getBoundingClientRect().height), content: t.scrollHeight }; });
  check('phone: and drawn at the height their rows need', mBox.drawn >= mBox.content - 2, JSON.stringify(mBox));
  const overflow = await m.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  eq('phone: the sheet does not scroll sideways', overflow, true);
  if (shotsDir) await m.page.screenshot({ path: path.join(shotsDir, 'compare-390.png') });
  eq('phone comparison page errors', m.errors, []);
  await m.context.close();
}

// ---------------------------------------------------------------- the evidence on the chart
// Every anchor is a DATE the run archived. The two mutants here are the point:
// a series with a later observation appended must still mark the SIGNAL day,
// and a series missing the bar before the signal must mark the one that did
// print, not the previous calendar day.
async function checkEvidence(browser, base, data) {
  console.log('-- the recorded evidence, on the chart');
  const b = data.bursts[0], series = b.series, session = data.run.session;
  const markOf = (page, sel) => page.locator(sel || '#chart-mount .sc-chart--stock').getAttribute('data-highlight');
  const levels = (page) => page.evaluate(() => {
    const svg = document.querySelector('#chart-mount svg');
    const at = (k) => { const l = svg.querySelector(`[data-level="${k}"]`); return l ? l.getAttribute('y1') : null; };
    return { stop: at('stop'), trigger: at('trigger'), close: at('close'), grid: Array.from(svg.querySelectorAll('.sc-chart__grid')).map((g) => g.getAttribute('y1')).join(',') };
  });
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${b.ticker}` });

  eq('a burst offers the base, the burst day and the prior day', await page.locator('#detail .ss-evidence [data-anchor]').evaluateAll((e) => e.map((x) => x.dataset.anchor)), ['base', 'burst', 'prior']);
  eq('nothing is marked until the reader asks', await markOf(page), null);
  const geomBefore = await levels(page);

  // the base: exactly the archived start and end
  await page.click('#detail .ss-evidence [data-anchor="base"]'); await page.waitForTimeout(300);
  eq('Base marks exactly the archived base dates', await markOf(page), `${b.quality.base.start}/${b.quality.base.end}`);
  eq('the marker is drawn once', await count(page, '#chart-mount .sc-chart__evidence-band'), 1);
  eq('marking a date range moves no price', await levels(page), geomBefore);
  const explain = await text(page, '#detail .ss-evidence__explain');
  check('the explanation names the dates it marked', explain.includes(dateWords(b.quality.base.start)) && explain.includes(dateWords(b.quality.base.end)), explain.slice(0, 160));
  check('and prints the recorded measurement', explain.includes(`${b.quality.base.sessions} sessions`) && explain.includes(usd(b.quality.base.low) + '–' + usd(b.quality.base.high)), explain.slice(0, 300));
  const cons = b.quality.checks.find((c) => c.key === 'consolidation');
  check('with the producer\'s own threshold and verdict, not the page\'s arithmetic', explain.includes(cons.threshold) && explain.includes(cons.display), explain.slice(0, 600));
  eq('the verdict is the checklist\'s', await page.locator('#detail .ss-evidence__check[data-check="consolidation"]').getAttribute('data-verdict'), cons.pass ? (cons.marginal ? 'partial' : 'pass') : 'fail');

  // the burst day and the prior day, by observation
  await page.click('#detail .ss-evidence [data-anchor="burst"]'); await page.waitForTimeout(250);
  eq('Burst day marks the session the record was published for', await markOf(page), session);
  await page.click('#detail .ss-evidence [data-anchor="prior"]'); await page.waitForTimeout(250);
  const priorDate = series[series.findIndex((x) => x.date === session) - 1].date;
  eq('Prior day marks the bar before it in the archived series', await markOf(page), priorDate);
  check('and prints that bar\'s own prices', (await text(page, '#detail .ss-evidence__explain')).includes('close ' + usd(series[series.findIndex((x) => x.date === session) - 1].c)), await text(page, '#detail .ss-evidence__explain'));

  // clearing, and the mode it must survive
  await page.click('#detail .ss-evidence [data-anchor="prior"]'); await page.waitForTimeout(200);
  eq('pressing the pressed control clears the mark', await markOf(page), null);
  await page.click('#detail .ss-evidence [data-anchor="base"]'); await page.waitForTimeout(250);
  await page.click('#detail .sc-tab[data-mode="line"]'); await page.waitForTimeout(350);
  eq('a mode change keeps the mark on the same dates', [await page.locator('#chart-mount .sc-chart--stock').getAttribute('data-mode'), await markOf(page)], ['line', `${b.quality.base.start}/${b.quality.base.end}`]);
  await page.click('#detail .sc-tab[data-mode="setup"]'); await page.waitForTimeout(300);
  await page.click('#detail [data-evidence-clear]'); await page.waitForTimeout(200);
  eq('Clear clears it', [await markOf(page), await count(page, '#chart-mount .sc-chart__evidence-band')], [null, 0]);

  // the checklist tile is the SAME mechanism, not a second one
  await openAll(page, '#detail details');
  // The record dates a base, a signal session and the bar before it. Everything
  // else the checklist measures -- the prior leg's linearity, the trend's age,
  // the run of up days -- has numbers and no dates, so ALL of those must stay
  // tiles: naming one of them here would leave the others free to be drawn.
  const tileTag = (want) => page.locator('#detail .ss-checks [data-check]').evaluateAll((e, w) => e.filter((x) => (x.tagName === 'BUTTON') === w).map((x) => x.dataset.check).sort(), want);
  eq('exactly the checks the record dates are ways onto the chart', await tileTag(true), ['close_near_high', 'consolidation', 'narrow_or_negative', 'range_expansion', 'volume']);
  eq('and every undated one stays a tile', await tileTag(false), ['linearity', 'two_days', 'young_trend']);
  await page.click('#detail .ss-checks [data-check="consolidation"]'); await page.waitForTimeout(350);
  eq('the tile marks the base through the one mechanism', await markOf(page), `${b.quality.base.start}/${b.quality.base.end}`);
  eq('and the evidence control shows as pressed', await page.locator('#detail .ss-evidence [data-anchor="base"]').getAttribute('aria-pressed'), 'true');
  await page.click('#detail .ss-checks [data-check="volume"]'); await page.waitForTimeout(300);
  eq('a burst-day check marks the burst day', await markOf(page), session);

  // choosing another stock rebinds: nothing of the last one survives
  const other = data.bursts[1];
  await clickPick(page, other.ticker);
  eq('a new stock starts unmarked', await markOf(page), null);
  eq('and its evidence controls are unpressed', await page.locator('#detail .ss-evidence [data-anchor]').evaluateAll((e) => e.map((x) => x.getAttribute('aria-pressed'))), ['false', 'false', 'false']);
  await page.click('#detail .ss-evidence [data-anchor="base"]'); await page.waitForTimeout(300);
  eq('the new stock marks its OWN archived base', await markOf(page), `${other.quality.base.start}/${other.quality.base.end}`);

  // a coil offers its box, and nothing that is not recorded for it
  const coil = data.watchlist.top[0];
  await go(page, `#/explore/setting-up/${coil.ticker}`); await page.waitForTimeout(300);
  eq('a coil offers the box alone', await page.locator('#detail .ss-evidence [data-anchor]').evaluateAll((e) => e.map((x) => x.dataset.anchor)), ['box']);
  await page.click('#detail .ss-evidence [data-anchor="box"]'); await page.waitForTimeout(300);
  eq('and marks the recorded box dates', await markOf(page), `${coil.box.start}/${coil.box.end}`);
  check('saying it is measured and not graded', (await text(page, '#detail .ss-evidence__explain')).includes('measured, not graded'), await text(page, '#detail .ss-evidence__explain'));
  await openAll(page, '#detail details');
  await page.click('#detail .ss-fact__show[data-anchor="box"]'); await page.waitForTimeout(300);
  eq('the coil\'s box row is the same mechanism too', await markOf(page), `${coil.box.start}/${coil.box.end}`);
  if (shotsDir) await page.locator('#detail .ss-chart-panel').screenshot({ path: path.join(shotsDir, 'evidence-1280.png') });
  eq('evidence page errors', errors, []);
  await context.close();

  // THE BURST DAY IS THE SIGNAL, not the last bar: a later observation appended
  // to the frame must not move it (this is what an index-from-the-end reads)
  const later = { date: '2026-09-11', o: series[series.length - 1].c, h: series[series.length - 1].c * 1.02, l: series[series.length - 1].c * 0.99, c: series[series.length - 1].c * 1.01, v: 1000000 };
  const app = await openMutant(browser, base, data, (c) => { c.bursts[0].series = c.bursts[0].series.concat([later]); }, { lens: 'all' });
  await go(app.page, `#/explore/bursts/${b.ticker}`); await app.page.waitForTimeout(300);
  await app.page.click('#detail .ss-evidence [data-anchor="burst"]'); await app.page.waitForTimeout(300);
  eq('a later observation does not move the burst day', await markOf(app.page), session);
  await app.page.click('#detail .ss-evidence [data-anchor="prior"]'); await app.page.waitForTimeout(300);
  eq('nor the prior day', await markOf(app.page), priorDate);
  eq('appended-observation page errors', app.errors, []);
  await app.close();

  // THE PRIOR DAY IS THE PREVIOUS OBSERVATION, not the previous date: with the
  // bar before the signal missing, it is the one that did print
  const gap = await openMutant(browser, base, data, (c) => {
    const s = c.bursts[0].series, i = s.findIndex((x) => x.date === session);
    s.splice(i - 1, 1);
  }, { lens: 'all' });
  await go(gap.page, `#/explore/bursts/${b.ticker}`); await gap.page.waitForTimeout(300);
  await gap.page.click('#detail .ss-evidence [data-anchor="prior"]'); await gap.page.waitForTimeout(300);
  const gapPrior = series[series.findIndex((x) => x.date === session) - 2].date;
  eq('the prior day is the previous bar that printed', await markOf(gap.page), gapPrior);
  check('and it is not the previous calendar day', gapPrior !== priorDate, [gapPrior, priorDate]);
  eq('gap page errors', gap.errors, []);
  await gap.close();

  // evidence outside the range on screen: offered, never taken silently
  const far = await openMutant(browser, base, data, (c) => {
    const s = c.bursts[0].series, q = c.bursts[0].quality.base;
    q.start = s[2].date; q.end = s[7].date;
    q.low = Math.min(...s.slice(2, 8).map((x) => x.l)); q.high = Math.max(...s.slice(2, 8).map((x) => x.h));
  }, { lens: 'all' });
  await go(far.page, `#/explore/bursts/${b.ticker}`); await far.page.waitForTimeout(300);
  await far.page.click('#detail .ss-evidence [data-anchor="base"]'); await far.page.waitForTimeout(300);
  await far.page.click('#detail .sc-tab[data-range="60"]'); await far.page.waitForTimeout(400);
  eq('a range that does not hold the evidence draws no marker', [await markOf(far.page), await count(far.page, '#chart-mount .sc-chart__evidence-band')], [null, 0]);
  eq('and the explanation offers the range that does', await count(far.page, '#detail [data-anchor-state="out-of-range"] [data-show-range]'), 1);
  await far.page.click('#detail [data-show-range]'); await far.page.waitForTimeout(400);
  const farBase = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  eq('taking the offer shows it', [await far.page.locator('#chart-mount .sc-chart--stock').getAttribute('data-range'), await markOf(far.page)],
    ['setup', `${farBase.bursts[0].series[2].date}/${farBase.bursts[0].series[7].date}`]);
  eq('out-of-range page errors', far.errors, []);
  await far.close();

  // no dates, no anchor: the words stand and nothing is drawn for them
  const nodate = await openMutant(browser, base, data, (c) => { delete c.bursts[0].quality.base.start; delete c.bursts[0].quality.base.end; }, { lens: 'all' });
  await go(nodate.page, `#/explore/bursts/${b.ticker}`); await nodate.page.waitForTimeout(300);
  eq('without base dates there is no Base control', await count(nodate.page, '#detail .ss-evidence [data-anchor="base"]'), 0);
  await openAll(nodate.page, '#detail details');
  eq('and its check is not clickable either', await nodate.page.locator('#detail .ss-checks [data-check="consolidation"]').evaluateAll((e) => e.map((x) => x.tagName)), ['DIV']);
  check('while the checklist still prints its measurement', (await text(nodate.page, '#detail .ss-checks')).length > 20, 'checks');
  eq('no-dates page errors', nodate.errors, []);
  await nodate.close();

  // no bars at all: the evidence keeps its words and says there is no chart
  const nobars = await openMutant(browser, base, data, (c) => { c.bursts[0].series = []; }, { lens: 'all' });
  await go(nobars.page, `#/explore/bursts/${b.ticker}`); await nobars.page.waitForTimeout(300);
  eq('without bars the base is still offered as text', await count(nobars.page, '#detail .ss-evidence [data-anchor="base"]'), 1);
  eq('but the burst day, which is read off the frame, is not', await count(nobars.page, '#detail .ss-evidence [data-anchor="burst"]'), 0);
  await nobars.page.click('#detail .ss-evidence [data-anchor="base"]'); await nobars.page.waitForTimeout(250);
  const noChart = await text(nobars.page, '#detail .ss-evidence__explain');
  check('the measurement is printed and the missing chart is named', noChart.includes(`${b.quality.base.sessions} sessions`) && noChart.includes('no chart to sit on'), noChart.slice(0, 300));
  eq('and no chart is invented for it', await count(nobars.page, '#chart-mount .sc-chart--stock'), 0);
  eq('no-bars evidence page errors', nobars.errors, []);
  await nobars.close();
}

async function main() {
  const chromium = await loadChromium();
  if (!chromium) { console.log('playwright is not installed: npm install --no-save playwright'); process.exit(1); }
  for (const v of VARIANTS) if (!existsSync(path.join(FIXTURES, `${v}.json`))) { console.log(`missing fixture ${v}.json -- run python tools/make_fixture.py`); process.exit(1); }
  const { server, base } = await serve();
  const browser = await chromium.launch();
  try {
    let full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
    for (const v of VARIANTS) {
      if (!runs(v)) continue;
      const data = JSON.parse(await readFile(path.join(FIXTURES, `${v}.json`), 'utf8'));
      await checkVariant(browser, base, v, data);
    }
    if (runs('mobile')) await checkMobile(browser, base, full);
    if (runs('modes')) await checkModes(browser, base, full);
    if (runs('lens')) await checkLens(browser, base, full);
    if (runs('compare')) await checkCompare(browser, base, full);
    if (runs('evidence')) await checkEvidence(browser, base, full);
    if (runs('map')) await checkMap(browser, base, full);
    if (runs('volume')) await checkVolumeReadings(browser, base, full);
    if (runs('mapscale')) await checkMapScale(browser, base, full);
    if (runs('following')) await checkFollowing(browser, base, full);
    if (runs('ticket')) await checkTicketPrices(browser, base, full);
    if (runs('states')) await checkStates(browser, base, full);
  } finally {
    await browser.close();
    server.close();
  }
  console.log(`\n${checks - failures}/${checks} page checks passed${shotsDir ? '; screenshots in ' + shotsDir : ''}`);
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
