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
import { checkActionability } from './actionability_cases.mjs';
import { checkEvidenceFocus } from './evidence_focus_cases.mjs';
import { checkReading } from './reading_cases.mjs';
import { checkExplorePanes } from './explore_pane_cases.mjs';
import { checkFollowedPlan } from './followed_plan_cases.mjs';
import { checkScorecard } from './scorecard_cases.mjs';
import { readFile, stat, mkdir, writeFile, unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'page');
const VARIANTS = ['full', 'degraded', 'notrade', 'yellow', 'red', 'closed', 'next'];
// the sequels a follow-through reading needs beside the nights: the same
// market one session on, and that session re-run on later bars
const SEQUELS = ['next', 'revised'];
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
// evidence/map/reach/mobile/modes/following/through/session/refresh/volume/mapscale/ticket/states). It is for
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
  if (opts.beforeLoad) await opts.beforeLoad(page, context);
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
// where a check's whole point is that an element EXISTS and says something,
// absence is the failure: read it without waiting out the locator's timeout
const said = async (page, sel) => (await page.locator(sel).count()) ? page.locator(sel).first().innerText() : '';
const attr = async (page, sel, name) => (await page.locator(sel).count()) ? page.locator(sel).first().getAttribute(name) : null;
// a click whose target may be the very thing a mutant removed: it is checked
// for, not waited for, so the suite reports a missing control instead of hanging
const tap = async (page, sel, name) => {
  if (sel.startsWith('#following ') && !(await page.locator('#view-setups').isVisible())) { await go(page, '#/setups'); }
  const there = !!(await page.locator(sel).count());
  check(name, there, there ? undefined : `no ${sel} to click`);
  if (!there) return false;
  await page.locator(sel).first().click(); await page.waitForTimeout(200); return true;
};
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
const dateShort = (iso) => { const dt = new Date(iso + 'T12:00:00Z'); return dt.getUTCDate() + ' ' + MON[dt.getUTCMonth()]; };
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
  check(`${variant} ${b.ticker} why: counts the checks`, why.includes(`of ${q.checks.length} recorded criteria pass`), why);
  if (miss) check(`${variant} ${b.ticker} why: names the miss`, why.includes(miss.label), miss.label);
  if (b.claude && b.claude.source === 'claude') {
    check(`${variant} ${b.ticker} why: recorded grade outcome`, why.includes('checklist ' + b.grade_mechanical + '; published ' + b.grade), why);
    check(`${variant} ${b.ticker} why: commentary stays in Provenance`, !why.includes(b.claude.reason), why);
    const provenance = await text(page, '#disc-provenance');
    check(`${variant} ${b.ticker} reader authority`, provenance.includes('commentary is unverified') && provenance.includes('Recorded checklist criteria govern thresholds'), provenance);
  }
  const need = await text(page, '#detail .ss-decision__item[data-item="need"]');
  const entry = b.plan ? (b.plan.exit_schedule || []).find((s) => s.key === 'entry' || s.day === 1) : null;
  if (entry) check(`${variant} ${b.ticker} need: the day-1 instruction`, need.toLowerCase().includes(entry.instruction.slice(1, 60).toLowerCase()), need);
  if (status !== 'ticket') check(`${variant} ${b.ticker} need: says no ticket`, /No ticket tonight|This record offers no entry:/.test(need), need);
  const wait = await text(page, '#detail .ss-decision__item[data-item="wait"]');
  if (b.plan && b.plan.pre_open_check) check(`${variant} ${b.ticker} wait: the pre-open check`, wait.toLowerCase().includes(b.plan.pre_open_check.slice(1, 60).toLowerCase()), wait);
  if (b.plan) check(`${variant} ${b.ticker} wait: the stop`, wait.includes(usd(b.plan.stop)), wait);
  const risk = await text(page, '#detail .ss-decision__item[data-item="risk"]');
  if (b.claude && b.claude.key_risk) check(`${variant} ${b.ticker} risk: attributed commentary`, risk.includes('Unverified chart-reader commentary: ' + b.claude.key_risk.replace(/\.$/, '')), risk);
  if (!(b.series || []).length) check(`${variant} ${b.ticker} risk: names the missing bars`, risk.includes('No bars are archived'), risk);
  // the action area: a ticket, or the reason there is none; never "buy now"
  const action = await text(page, '#detail .ss-action');
  const ticketAttr = await page.locator('#detail .ss-action').getAttribute('data-ticket');
  check(`${variant} ${b.ticker} action never says buy now`, !/buy now/i.test(action), action);
  const btn = await text(page, '#detail .ss-action [data-open]');
  if (status === 'ticket' && !blocked) {
    eq(`${variant} ${b.ticker} action carries the order`, ticketAttr, 'order');
    const order = b.plan.order_json;
    eq(`${variant} ${b.ticker} action prints recorded order fields`, await page.locator('#detail [data-plan-value]').allTextContents(),
      [usd(order.stop_price), usd(order.limit_price), usd(order.then.stop_price), order.quantity + ' shares']);
    eq(`${variant} ${b.ticker} action button`, btn, 'Plan details');
  } else if (status === 'ticket') {
    eq(`${variant} ${b.ticker} action withholds the order on a blocked page`, ticketAttr, 'blocked');
    eq(`${variant} ${b.ticker} action button`, btn, 'Inspect recorded plan');
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
  const want = q.checks.map((c) => (q.vetoes.includes('up_days') && c.key === 'two_days') || (q.vetoes.includes('not_linear') && c.key === 'linearity') ? 'veto' : c.pass ? (c.marginal ? 'partial' : 'pass') : (String(c.status).toLowerCase() === 'unmeasured' ? 'not measured' : c.partial || c.marginal || String(c.status).toLowerCase() === 'partial' ? 'partial' : 'fail'));
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
  if (b.evidence) {
    const recorded = await text(page, '[data-plan-evidence]');
    check(`${variant} ${b.ticker} evidence recorded`, recorded.includes('Evidence recorded') && recorded.includes('split-adjusted'), recorded);
    check(`${variant} ${b.ticker} evidence distinguishes ticket from quality`, recorded.includes(b.evidence.gate.ticket ? 'A conditional ticket was published.' : 'No ticket:'), recorded);
    check(`${variant} ${b.ticker} technical reference matches publication`, prov.includes(b.evidence.id), 'evidence id');
  }
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} claude read`, prov.includes(b.claude.reason), 'reason');
  if (b.claude && b.claude.source === 'claude') check(`${variant} ${b.ticker} a fixture's reader reply is labelled simulated`, prov.includes('simulated chart-reader reply') && !prov.includes('claude read the chart'), prov.slice(0, 120));
  if ((b.series || []).length) check(`${variant} ${b.ticker} chart panel carries the demo chip`, (await text(page, '#detail .ss-chart-panel__head')).includes('demo data'), 'chip');
  else check(`${variant} ${b.ticker} says no usable model judgement`, prov.includes('no usable chart-reader judgement'), 'nomodel');
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
  check(`${variant} ${r.ticker} why: the coil's measures`, why.includes(`${r.quiet_days} narrow-range days`) && why.includes(`${r.range_pct}% range`), why);
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
  const { context, page, errors, aborted } = await open(browser, base, `/tests/fixtures/page/${variant}.json`, variant === 'closed' ? '2026-09-07T22:31:00Z' : new Date(Date.parse(data.generated) + 60000).toISOString(), 1280);
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
  check(`${variant} scan scope uses this record`, (await text(page, '#cover-dek')).includes('Found ' + run.bursts + ' burst candidates'));
  check(`${variant} original summary remains inspectable`, (await page.locator('#cover-original').textContent()).includes(data.cover.dek));
  eq(`${variant} title`, await page.title(), 'SpicyStock · ' + data.cover.h1);
  eq(`${variant} action`, await text(page, '#cover-action'), data.cover.action_label);
  const target = data.cover.action_target;
  check(`${variant} cover action target exists`, (await page.locator(target).count()) === 1, target);
  // the regime sits with the VERDICT it belongs to; the two facts beside them
  // are about time, and each carries its own chip
  const regimeLine = await text(page, '#cover-regime');
  check(`${variant} the verdict names the regime`, regimeLine.includes(data.breadth.regime.verdict.toUpperCase()), regimeLine);
  check(`${variant} and the ratio`, regimeLine.includes(String(data.breadth.ratio_10d)), regimeLine);
  const facts = await text(page, '#market-facts');
  check(`${variant} the data line names the measured session and when it published`,
    facts.includes(dateWords(data.run.session)) && /published \d+:\d\d [AP]M ET/.test(facts), facts);
  check(`${variant} the plan line names the session the plans are for`,
    facts.includes(dateWords(data.run.timing.applicable_session)), facts);
  check(`${variant} and the two carry one chip each, so neither covers the other`,
    (await page.locator('#market-facts [data-fact="data"] .sc-chip').count()) === 1 &&
    (await page.locator('#market-facts [data-fact="plan"] .sc-chip').count()) === 1,
    'a fact without its own chip');
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
      await page.locator('#detail .ss-action [data-open]').click();
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
      const want = b.quality.checks.map((c) => (b.quality.vetoes.includes('up_days') && c.key === 'two_days') || (b.quality.vetoes.includes('not_linear') && c.key === 'linearity') ? 'veto' : c.pass ? (c.marginal ? 'partial' : 'pass') : (String(c.status).toLowerCase() === 'unmeasured' ? 'not measured' : c.marginal ? 'partial' : 'fail'));
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
    // the whole-share contract: the sentence names the sale in shares, and the
    // record's own counts are whole and add up to the position. `remaining N`
    // was asserted here until the `next` fixture showed the phrase belongs to
    // ONE status's wording (sell_into_strength's), so the check passed on an
    // incidental fact about the fixture rather than on the rule it names.
    if (typeof p.sold === 'number' && p.sold > 0 && p.remaining > 0) check(`${variant} ${p.ticker} whole-share sale in the instruction`,
      body.includes(`${p.sold} of ${p.shares}`) && Number.isInteger(p.sold) && Number.isInteger(p.remaining) && p.sold + p.remaining === p.shares,
      `${p.instruction} [${p.sold}+${p.remaining} of ${p.shares}]`);
  }
  if (!data.open_plans.length) check(`${variant} says no open plans`, (await text(page, '#hold-rows')).includes('No open model plans'), 'hold');
  const record = await text(page, '#record-card');
  const sc = data.scorecard;
  check(`${variant} scorecard plans`, record.includes(`plans\n${sc.plans}`) || record.includes(`plans ${sc.plans}`), record.slice(0, 200));
  check(`${variant} scorecard readable chip`, record.includes(sc.readable ? 'readable' : 'not yet readable'), 'chip');
  check(`${variant} scorecard settled count`, record.includes(`${sc.settled} settled`), record.slice(0, 300));
  check(`${variant} scorecard uncertain count`, record.includes(`${sc.uncertain} uncertain`), record.slice(0, 300));
  if (sc.uncertain) for (const r of sc.uncertain_reasons) check(`${variant} scorecard uncertain reason ${r.kind}`, (await page.locator('#scorecard-uncertain').textContent()).includes(`${r.count} ${r.words}`), r.kind);
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
  const methodBody = await text(page, '#method-body');
  check(`${variant} Method separates Dollar discovery and quality`, methodBody.includes('4% breakout or Dollar breakout') && methodBody.includes('below +4%') && methodBody.includes('A-quality is judged after discovery'), methodBody);
  check(`${variant} Method pins current sources without relabelling history`, methodBody.includes('May 21, 2015') && methodBody.includes('July 13, 2017') && methodBody.includes('Historical records keep their recorded rules.'), methodBody);
  eq(`${variant} Method links the dated source contract`, await page.locator('#method-body a').filter({ hasText: 'Current discovery sources' }).getAttribute('href'), 'https://github.com/spicyChicken59/SpicyStock/blob/main/knowledge/reaction-discovery.md');
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

  // the next action, whatever the view. The headline names the SESSION the
  // plans are for -- read off the record's own timing block, never off a word
  // the page happens to print -- because "tomorrow" is true for one evening
  // and wrong from the next midnight, on the very day it means.
  await go(page, '#/explore');
  const next = await text(page, '#next-h3'), forDay = dateWords(data.run.timing.applicable_session);
  if (variant === 'closed') check(`${variant} next: plans unchanged`, next.startsWith('Plans unchanged'), next);
  else if (data.breadth.regime.verdict === 'red') check(`${variant} next: no new longs`, next.startsWith('No new longs'), next);
  else if (withOrders.length) check(`${variant} next: review conditional tickets, for a named session`,
    next === `Review ${withOrders.length} conditional ticket${withOrders.length === 1 ? '' : 's'} for ${forDay}.`, next);
  else check(`${variant} next: nothing new, for a named session`, /^Nothing/.test(next) && next.includes(forDay), next);
  check(`${variant} next never names a deadline that has passed`, !/before 9:28 AM/.test(next) || await attr(page, 'html', 'data-ss-window') === 'upcoming',
    `${next} @ window ${await attr(page, 'html', 'data-ss-window')}`);

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
    const light = await open(browser, base, `/tests/fixtures/page/${variant}.json`, variant === 'closed' ? '2026-09-07T22:31:00Z' : new Date(Date.parse(data.generated) + 60000).toISOString(), 1280, { theme: 'light' });
    await light.page.screenshot({ path: path.join(shotsDir, `${variant}-1280-light.png`), fullPage: true });
    eq(`${variant} light page errors`, light.errors, []);
    await light.context.close();
  }
}

// A column card must keep its actions underneath its selection button. Column
// wrapping can put the actions under the next card while they still count as
// visible DOM controls, so inspect the actual rendered bounds.
async function checkCardTools(page, label) {
  const cards = await page.locator('#pick-list .ss-pick-item').evaluateAll((items) => items.slice(0, 2).map((item) => {
    const box = (e) => { const r = e.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; };
    const tools = item.querySelector('.ss-pick__tools');
    return { ticker: item.querySelector('.ss-pick').dataset.ticker, item: box(item), pick: box(item.querySelector('.ss-pick')),
      tools: box(tools), buttons: [...tools.querySelectorAll('button')].map(box) };
  }));
  check(`${label}: both cards keep Save and Compare below their own selection`, cards.length === 2 && cards.every((c) =>
    c.buttons.length === 2 && c.tools.top >= c.pick.bottom - 1 && c.tools.bottom <= c.item.bottom + 1 &&
    c.buttons.every((b) => b.left >= c.item.left - 1 && b.right <= c.item.right + 1 && b.bottom <= c.item.bottom + 1)), JSON.stringify(cards));
}

// the phone: the stage and stock controls in the first screen, a rail of cards, the chooser dialog
async function checkMobile(browser, base, data) {
  console.log('-- the phone');
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844 });
  if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.screenshot({ path: path.join(shotsDir, 'full-390-dark.png') }); await page.screenshot({ path: path.join(shotsDir, 'full-390-dark-full.png'), fullPage: true }); }
  await checkCardTools(page, '390 dark');
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
    const p = bar.querySelector('p:last-of-type'), btn = bar.querySelector('.ss-action__controls');
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
  for (const [width, theme] of [[390, 'light'], [320, 'dark'], [320, 'light']]) {
    const rail = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, width, { height: 844, theme, lens: 'all' });
    await checkCardTools(rail.page, `${width} ${theme}`);
    if (shotsDir) {
      await rail.page.locator('#pick-list [data-save-setup]').first().focus();
      await rail.page.screenshot({ path: path.join(shotsDir, `card-tools-${width}-${theme}.png`) });
    }
    eq(`${width} ${theme} card tools page errors`, rail.errors, []);
    await rail.context.close();
  }
  // The first screen now answers whether there is an entry and shows its
  // recorded levels. The unchanged full-height chart follows that decision.
  const desk = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280);
  const d = async (sel) => desk.page.locator(sel).first().boundingBox();
  const deskStages = await desk.page.locator('#stages .ss-stage__sub').evaluateAll((els) => els.map((e) =>
    ({ text: e.innerText.replace(/\s+/g, ' ').trim(), drawn: e.getClientRects().length > 0 })));
  eq('the phone and the desktop stage cards carry the same ticket counts', phoneStages, deskStages);
  const bar = await d('#market-bar'), st = await d('#stages'), firstPick = await d('#pick-list .ss-pick'), chart = await d('#chart-mount');
  // Capture the page before any detail-targeting action, including enough
  // row geometry to distinguish font wrapping from a changed page offset.
  console.log('  desktop first-screen geometry:', JSON.stringify({ bar, stages: st, firstPick,
    rows: await desk.page.locator('.ss-picks__head > *').evaluateAll(es => es.filter(e => e.getClientRects().length).map(e => {
      const r = e.getBoundingClientRect(); return { text: e.innerText, y: r.y, height: r.height, width: r.width };
    })) }));
  check('desktop: the market bar, the stages and the first stock are in the first screen', bar && st && firstPick && bar.y >= 0 && st.y + st.height <= 900 && firstPick.y + firstPick.height <= 900, JSON.stringify([bar, st, firstPick]));
  const levelsBox = await desk.page.locator('#detail .ss-action__levels').boundingBox();
  check('desktop: the recorded action levels fit in the first screen', levelsBox && levelsBox.y + levelsBox.height <= 900, JSON.stringify(levelsBox));
  check('desktop: the chart follows the action summary', chart && levelsBox && chart.y > levelsBox.y + levelsBox.height, JSON.stringify(chart));
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
  eq('nothing followed yet', await text(page, '#following-jump'), 'My setups · 0');
  check('the follow button names the suggested size', (await text(page, '#detail .ss-follow')).includes(`${trade.plan.shares} shares suggested`), await text(page, '#detail .ss-follow'));
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('one click follows', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'following');
  eq('the shelf shows the setup', await count(page, `#following .ss-followed[data-ticker="${trade.ticker}"]`), 1);
  eq('the count control moves', await text(page, '#following-jump'), 'My setups · 1');
  const card = () => text(page, `#following .ss-followed[data-ticker="${trade.ticker}"]`);
  check('the card keeps the saved plan levels', (await card()).includes('stop ' + usd(trade.plan.stop)) && (await card()).includes('limit ' + usd(trade.plan.entry_high)), await card());
  check('and dates the status it archived', (await card()).includes(dateShort(data.run.session) + ' record'), await card());
  check('the card shows the signal close under what was frozen', (await card()).includes(usd(trade.close)) && (await card()).includes('at the signal'), await card());
  check('and says plainly that nothing later has been seen yet', (await card()).includes('since the signal') && (await card()).includes('No later close has been observed'), await card());
  const ownWords = () => page.locator(`#following .ss-followed[data-ticker="${trade.ticker}"]`).first().evaluate((c) => { const k = c.cloneNode(true); k.querySelectorAll('.ss-followed__note').forEach((n) => n.remove()); return k.innerText; });
  check('the card never asserts a fill or a holding in its own words', !/\b(bought|filled|held|sold|stopped out)\b/i.test(await ownWords()), await ownWords());
  check('the record’s sentence on the card is quoted and labelled as the record’s', /the record says\s*“/.test(await card()), await card());
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
  eq('undo removes the setup', [await page.locator('#detail .ss-follow').getAttribute('data-follow'), await count(page, '#following .ss-followed'), await text(page, '#following-jump')], ['not-following', 0, 'My setups · 0']);
  // a blocked write says so and never shows Following
  await page.evaluate(() => { window.__setItem = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error('blocked'); }; });
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('a blocked write is not a follow', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'not-following');
  check('a blocked write is named', (await text(page, '#detail .ss-follow')).includes('Could not confirm the save'), await text(page, '#detail .ss-follow'));
  eq('following page errors', errors, []);
  await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200);
  eq('a second blocked write does not stack its sentence', await count(page, '#detail .ss-follow .ss-follow__warn'), 1);
  await page.evaluate(() => { Storage.prototype.setItem = window.__setItem; });
  if (shotsDir) { await go(page, `#/explore/bursts/${trade.ticker}`); await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(200); eq('the store works again once unblocked', await page.locator('#detail .ss-follow').getAttribute('data-follow'), 'following'); await page.locator('#detail .ss-action').screenshot({ path: path.join(shotsDir, 'follow-action-1280.png') }); await go(page, '#/setups'); await page.locator('#following').screenshot({ path: path.join(shotsDir, 'following-1280.png') }); }
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
  coverage_thin: 'Some intended stocks lack usable session bars',
  claude_unavailable: 'No usable chart-reader judgement',
  claude_partial: 'Chart-reader judgements were accepted',
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
    // the reason is the one shared answer's, which names the state it is in
    // (docs/app.js stateWords()); asserted by that word rather than by a fixed
    // sentence, so the check is about the rule and not about its wording
    const stateWord = { pending: 'waiting for tonight\u2019s run', failed: 'without a verdict' }[state] || 'stale';
    check(`${name} the plan says why, in the state's own word`,
      (await text(page, '#disc-plan')).includes(stateWord), (await text(page, '#disc-plan')).slice(0, 140));
    eq(`${name} and offers no copy control`, await count(page, '#disc-plan [data-copy]'), 0);
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
        check('the card, the detail line and the scan table print the checklist’s copy', r.card.includes('vol ' + q.toFixed(1) + '×') && r.sub.includes('on ' + q.toFixed(1) + '× prior-session volume') && r.table.includes(q.toFixed(1) + '× vol'), [r.card, r.sub, r.table]);
        check('the measurements say the ratio was read from the checklist', r.facts.includes(q.toFixed(1) + '× volume') && r.facts.includes('read from the checklist'), r.facts.slice(0, 300));
        eq('the chart’s burst label carries the checklist’s copy', r.labels, [(Math.round(q * 10) / 10) + '× vol']);
      }
      if (field === 'observations') check('without the observation block the shelf still renders', (await count(page, '#following .ss-following__empty')) === 1 || (await count(page, '#following .ss-followed')) >= 0, 'shelf');
      if (field === 'bursts.series') {
        eq('without browser bars the first burst offers its retained source', await count(page, '#detail [data-load-chart]'), 1);
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
  // A clock re-reading over the no-record page used to repaint the market bar
  // with "No verdict." over the sentence saying the record could not be read:
  // `failed()` leaves `current` a stub so the saved setups still read, and that
  // stub has a `run`, so "is there a record" could not be asked of it. The
  // events are fired here because a real browser fires them on its own timing
  // -- this failed on a runner and passed in the sandbox until it was pinned.
  await page.evaluate(() => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('pageshow')); document.dispatchEvent(new Event('visibilitychange')); });
  await page.waitForTimeout(200);
  eq('missing record: a clock re-reading does not paint over it',
    [await text(page, '#cover-h1'), await page.getAttribute('html', 'data-ss-rendered')],
    ['The record could not be read.', 'error']);
  eq('and the re-reading refuses outright', await page.evaluate(() => window.SCStock.reclock()), false);
  eq('missing record: no stages to choose', await count(page, '#stages [data-empty="record"]'), 1);
  await page.locator('#nav a[data-view="record"]').click();
  await page.waitForTimeout(150);
  eq('missing record: the views still switch', await visibleView(page), ['view-record']);
  if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'no-record-1280-dark.png'), fullPage: true });
  await context.close();
}


// ------------------------------------------------------------ follow-through
// A setup followed on one night, read back over the nights after it. The
// records are the pipeline's own sequels (`next` and `revised`, the same
// market one session on, and the second a re-run of that session on later
// bars), so what is asserted here is what the run would actually write.
const FOLLOW_KEY = 'spicystock:following:demo:v1';
// a store written by the PREVIOUS version of this page: a v1 payload, with a
// size the reader set and a symbol no record here carries
const LEGACY = { version: 1, items: [{ id: 'burst:ZZZZ:2026-08-14:old-rules', ticker: 'ZZZZ', kind: 'burst', stage: 'bursts',
  session: '2026-08-14', rules_version: 'old-rules', saved_at: '2026-08-14T22:40:00.000Z', suggested_shares: 3, reference_shares: 5, demo: true,
  snapshot: { name: 'Legacy Holdings', close: 40.5, close_date: '2026-08-14', grade: 'A', score: 8.2, status: 'ticket', status_words: 'ticket',
    levels: { trigger: 40.5, limit: 41.2, stop: 38.9 }, instruction: 'Buy on a print over $40.50.', summary: 'A tight base and a clean burst.' } }] };
const seedStore = (page, payload) => page.evaluate(([k, v]) => { localStorage.setItem(k, JSON.stringify(v)); }, [FOLLOW_KEY, payload]);
const readStore = (page) => page.evaluate((k) => JSON.parse(localStorage.getItem(k)), FOLLOW_KEY);
const storeKeys = (page) => page.evaluate(() => Object.keys(localStorage).filter((k) => /following/.test(k)).sort());
// what the page READS (the store is only rewritten when something is written,
// so a repaired entry is repaired in the reading before it is on disk)
const shownObs = (page, ticker) => page.evaluate((t) => {
  const it = SCStock.follow.list().find((x) => x.ticker === t);
  return it ? (it.observations || []).map((o) => [o.date, o.c]) : null;
}, ticker);
const obsOf = (page, ticker) => page.evaluate(([k, t]) => {
  const it = JSON.parse(localStorage.getItem(k)).items.find((x) => x.ticker === t);
  return it ? (it.observations || []).map((o) => [o.date, o.c, o.from_session, !!o.revised, o.basis]) : null;
}, [FOLLOW_KEY, ticker]);
const rerender = async (page, data, now) => { await page.evaluate(([d, n]) => { SCStock.render(d, new Date(n)); }, [data, now]); await page.waitForTimeout(320); };
const followFrom = async (page, ticker) => {
  await go(page, `#/explore/bursts/${ticker}`);
  const add = page.locator('#detail .ss-follow button[data-follow-action="add"]');
  if (await add.count()) { await add.click(); await page.waitForTimeout(220); }
};
const cardOf = (page, t) => said(page, `#following .ss-followed[data-ticker="${t}"]`);
const openSaved = async (page, t) => {
  const opened = await tap(page, `#following .ss-followed[data-ticker="${t}"] [data-open-saved]`, `${t}: the card offers its saved setup`);
  if (opened) await page.waitForTimeout(280);
  return opened;
};
const closeSaved = (page) => tap(page, '#saved-close', 'the sheet offers a way out');
const savedTitle = (page) => said(page, '#saved-h2');
// by identity, for a shelf holding two saved setups on one symbol
const openSavedById = async (page, id, name) => { const ok = await tap(page, `#following .ss-followed[data-follow-id="${id}"] [data-open-saved]`, name); if (ok) await page.waitForTimeout(280); return ok; };

async function checkFollowThrough(browser, base, full) {
  console.log('-- follow-through: a saved setup after the night it was saved');
  const next = JSON.parse(await readFile(path.join(FIXTURES, 'next.json'), 'utf8'));
  const revised = JSON.parse(await readFile(path.join(FIXTURES, 'revised.json'), 'utf8'));
  const NEXT_NOW = '2026-09-11T22:31:00Z', LATER_NOW = '2026-09-11T23:20:00Z';
  const trade = full.trades[0], tradeRow = full.bursts.find((b) => b.ticker === trade);   // AAPL: the ticket, gone from the next record
  const withheld = (full.cash_budget.cut || []).find((c) => c.kind === 'withheld').ticker;   // TSLA: kept for observation
  const obsNext = next.observations.symbols[trade], obsRev = revised.observations.symbols[trade];
  check('the sequels are a genuinely newer record', next.run.session > full.run.session, `${full.run.session} -> ${next.run.session}`);
  check('and the revision is the SAME session on a different close', revised.run.session === next.run.session && obsRev.c !== obsNext.c, `${obsNext.c} -> ${obsRev.c}`);

  // ---- a store written by the previous version of this page
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
  await seedStore(page, LEGACY);
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(300);
  eq('a v1 store is upgraded in place', (await readStore(page)).version, 4);
  eq('and the payload it replaced is kept beside it', await storeKeys(page), [FOLLOW_KEY, FOLLOW_KEY + '.previous']);
  eq('verbatim', await page.evaluate((k) => JSON.parse(localStorage.getItem(k + '.previous')), FOLLOW_KEY), LEGACY);
  const legacy = (await readStore(page)).items[0];
  eq('the migrated setup keeps its size, its date and its levels',
    [legacy.reference_shares, legacy.saved_at, legacy.snapshot.levels.stop, legacy.snapshot.grade], [5, LEGACY.items[0].saved_at, 38.9, 'A']);
  eq('and has no chart, because none was saved then', [legacy.evidence, legacy.observations], [null, []]);
  check('the reader is told the upgrade happened', (await text(page, '#following-status')).includes('carried over'), await text(page, '#following-status'));
  // the copy is what makes the upgrade safe, so the case that matters is the
  // one where it does NOT take: the old payload must be left exactly as it was
  {
    const { context: c3, page: p3, errors: e3 } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
    await seedStore(p3, LEGACY);
    await p3.evaluate((k) => {
      const real = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, v) { if (key === k + '.previous') return; return real.call(this, key, v); };
    }, FOLLOW_KEY);
    await p3.evaluate(() => { SCStock.render(SCStock.data, new Date('2026-09-10T22:31:00Z')); });
    await p3.waitForTimeout(300);
    eq('a copy that does not take leaves the old payload exactly as it was', await readStore(p3), LEGACY);
    check('and says the list was left as it was', (await text(p3, '#following-status')).includes('left as it was'), await text(p3, '#following-status'));
    eq('while the setups still read', await count(p3, '#following .ss-followed'), 1);
    eq('copy-failure page errors', e3, []);
    await c3.close();
  }
  await openSaved(page, 'ZZZZ');
  check('its saved detail says the chart was not saved rather than drawing one',
    (await said(page, '#saved [data-chart="unsaved"]')).includes('Original chart was not saved') && !(await count(page, '#saved [data-panel="saved"]')), await said(page, '#saved [data-chart="unsaved"]'));
  check('and it is not a dead end: the levels and the reason are still there',
    (await said(page, '#saved .ss-saved__facts')).includes(usd(38.9)) && (await said(page, '#saved .ss-saved__quote')).includes('tight base'), await said(page, '#saved .ss-saved__facts'));
  // a chart may be RECOVERED for it, and only from the record that is this
  // signal: the same kind, symbol, session and rules identity
  await closeSaved(page); await page.waitForTimeout(250);
  {
    const { context: c4, page: p4, errors: e4 } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
    const sameSignal = Object.assign({}, LEGACY.items[0], { id: `burst:${trade}:${full.run.session}:${full.app.rules_version}`,
      ticker: trade, session: full.run.session, rules_version: full.app.rules_version,
      snapshot: Object.assign({}, LEGACY.items[0].snapshot, { close: tradeRow.close, close_date: full.run.session }) });
    const newerTicker = Object.assign({}, LEGACY.items[0], { id: `burst:${trade}:2026-08-14:${full.app.rules_version}`, ticker: trade });
    await seedStore(p4, { version: 1, items: [sameSignal, newerTicker] });
    await p4.reload(); await p4.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await p4.waitForTimeout(320);
    const back = (await readStore(p4)).items;
    const recovered = back.find((x) => x.id === sameSignal.id), other = back.find((x) => x.id === newerTicker.id);
    eq('a v1 follow gets its chart back from the record that IS its signal',
      [!!(recovered.evidence && recovered.evidence.series.length), recovered.evidence && recovered.evidence.recovered], [true, true]);
    check('bounded at the signal session, like one saved then',
      recovered.evidence.series.every((b) => b.date <= full.run.session), 'a bar after the signal was recovered');
    eq('and a v1 follow for the same TICKER under another session gets none', other.evidence, null);
    await openSavedById(p4, sameSignal.id, 'the recovered setup opens by its own identity');
    check('the sheet says the chart was recovered rather than saved then',
      (await said(p4, '#saved .sc-chart-caption')).includes('recovered from'), await said(p4, '#saved .sc-chart-caption'));
    eq('recovery page errors', e4, []);
    await c4.close();
  }

  // ---- a store this page does not understand is left alone
  await seedStore(page, { version: 99, items: [{ id: 'x', ticker: 'FUTURE', kind: 'burst', session: '2026-09-10', snapshot: {} }] });
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(300);
  eq('a newer schema is read as nothing rather than overwritten', (await readStore(page)).version, 99);
  check('and the reader is told why nothing can be saved', (await text(page, '#following-status')).includes('newer version'), await text(page, '#following-status'));
  // Closing a saved sheet now returns to My setups. Open the candidate before
  // checking its save refusal; a hidden/absent detail is not that protection.
  await go(page, `#/explore/bursts/${trade}`);
  await page.click('#detail .ss-follow button[data-follow-action="add"]').catch(() => {});
  await page.waitForTimeout(200);
  eq('a follow attempted over it writes nothing', (await readStore(page)).version, 99);
  check('and says so', (await text(page, '#detail .ss-follow')).includes('newer version'), await text(page, '#detail .ss-follow'));

  // ---- an entry with no identity is set aside by name, and the rest survive
  await seedStore(page, { version: 2, items: [LEGACY.items[0], { ticker: '', snapshot: {} }, Object.assign({}, LEGACY.items[0], { id: 'burst:YYYY:2026-08-14:old-rules', ticker: 'YYYY', observations: [{ date: 'not-a-date', c: 1 }, { date: '2026-08-20', c: 41 }] })] });
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(300);
  eq('a readable entry beside an unreadable one still shows', await count(page, '#following .ss-followed'), 2);
  check('the unreadable one is named, not silently dropped', (await text(page, '#following-status')).includes('set aside'), await text(page, '#following-status'));
  eq('and is kept where it can be recovered', await page.evaluate((k) => JSON.parse(localStorage.getItem(k + '.rejected')).items.length, FOLLOW_KEY), 1);
  eq('a malformed observation is dropped where the page reads it', await shownObs(page, 'YYYY'), [['2026-08-20', 41]]);
  check('and that is named too', (await text(page, '#following-status')).includes('no date or no price'), await text(page, '#following-status'));

  // ---- the journey proper
  await page.evaluate((k) => { ['', '.previous', '.rejected', '.corrupt'].forEach((s) => localStorage.removeItem(k + s)); }, FOLLOW_KEY);
  await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(250);
  const publicBefore = await page.evaluate(() => JSON.stringify([SCStock.data.scorecard, SCStock.data.trades, SCStock.data.cash_budget]));
  const again = next.bursts[0].ticker;   // NVDA: a burst in BOTH records, so two signals, two identities
  await followFrom(page, trade);
  await followFrom(page, withheld);
  await followFrom(page, again);
  const saved = (await readStore(page)).items.find((x) => x.ticker === trade);
  eq('a follow freezes the bars the record carried for that signal',
    [saved.evidence.series.length, saved.evidence.series[saved.evidence.series.length - 1].date], [tradeRow.series.length, full.run.session]);
  check('and only bars at or before the signal session', saved.evidence.series.every((b) => b.date <= full.run.session), 'a bar after the signal was saved');
  // the STORE holds that bound too, not only the page that wrote it: an item
  // whose saved chart has grown a later candle is read back without it, so a
  // frozen original cannot acquire a bar the reader never saw
  {
    const grown = JSON.parse(JSON.stringify(await readStore(page)));
    grown.items.forEach((it) => { if (it.evidence) it.evidence.series = it.evidence.series.concat([{ date: '2026-09-30', o: 1, h: 2, l: 1, c: 1.5, v: 1 }]); });
    await seedStore(page, grown);
    const back = await page.evaluate((t) => { const it = SCStock.follow.list().find((x) => x.ticker === t); return it.evidence.series.map((b) => b.date).slice(-2); }, trade);
    check('a bar printed after the signal is dropped when the store is read', back.every((d) => d <= full.run.session), JSON.stringify(back));
    await page.reload(); await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered')); await page.waitForTimeout(250);
  }
  eq('with the dated anchors drawn on them', saved.evidence.anchors.map((a) => a.key), ['base', 'burst', 'prior']);
  eq('and no observation yet: the signal day is the baseline, not an observation', saved.observations, []);

  // ---- a genuinely newer record
  await rerender(page, next, NEXT_NOW);
  check('the followed symbol has left the record', !(next.bursts || []).some((b) => b.ticker === trade), 'still a burst');
  check('public history carries the unchanged signal close', obsNext.history.some((b) => b.date === full.run.session && b.c === tradeRow.close));
  eq('one observation, dated by the market and not by the render', await obsOf(page, trade), [[obsNext.date, obsNext.c, next.run.session, false, 'match']]);
  const card = await cardOf(page, trade);
  check('the card answers what was followed and when its signal was', card.includes(trade) && card.includes(dateWords(full.run.session)), card.slice(0, 120));
  check('what the latest observation is, and when', card.includes(usd(obsNext.c)) && card.includes(dateWords(obsNext.date)), card.slice(0, 240));
  check('what changed against the signal close', card.includes(pctOf((obsNext.c / tradeRow.close - 1) * 100)), card.slice(0, 240));
  check('and whether it is current for the record on screen', card.includes('tonight’s record'), card.slice(0, 260));
  eq('the card marks it as current', await attr(page, `#following .ss-followed[data-ticker="${trade}"]`, 'data-observed'), 'current');
  check('the archived status is dated, so it cannot read as a ticket available now',
    card.includes(dateShort(full.run.session) + ' record'), card.slice(0, 160));
  check('the movement is still labelled as recorded prices, not a result', card.includes('not your result'), card.slice(0, 400));
  eq('one observation draws one point and no line', await page.locator(`#following .ss-followed[data-ticker="${trade}"] .ss-trail`).getAttribute('data-points'), '1');
  eq('and never a joining line', await count(page, `#following .ss-followed[data-ticker="${trade}"] .ss-trail polyline, #following .ss-followed[data-ticker="${trade}"] .ss-trail path`), 0);
  const updates = await said(page, '#following-updates');
  check('the updates summary says what its count is counted against', /Latest:/.test(updates) && updates.includes(dateShort(next.run.session)), updates);
  check('and never calls them alerts, trades or signals', !/alert|unread|new trade|buy signal/i.test(updates), updates);

  // idempotence: a re-render, a reload and a theme change add nothing
  const after = await obsOf(page, trade);
  await rerender(page, next, NEXT_NOW);
  eq('the same record rendered again adds no observation', await obsOf(page, trade), after);
  await page.evaluate(() => { document.documentElement.setAttribute('data-theme', 'light'); });
  await page.waitForTimeout(150);
  eq('a theme change adds none either', await obsOf(page, trade), after);

  // ---- the saved setup's own detail, for a symbol the record no longer has
  await openSaved(page, trade);
  eq('Open followed setup routes by the saved identity', await hash(page), '#/followed/' + encodeURIComponent(saved.id));
  eq('and opens THAT setup, not tonight’s first card', await savedTitle(page), trade);
  const facts = await said(page, '#saved .ss-saved__facts');
  check('with the original levels, unchanged by the newer record',
    facts.includes(usd(tradeRow.plan.stop)) && facts.includes(usd(tradeRow.plan.entry_high)) && facts.includes(usd(tradeRow.close)), facts.slice(0, 300));
  check('the grade it was given THEN, named as that record’s', facts.includes(tradeRow.grade) && facts.includes('in that record'), facts.slice(0, 200));
  // The aim is the 8-20% band quoted from the indicative entry, which the run
  // itself calls an estimate and never a fill; the trigger, the limit and the
  // stop in the same column are the ticket's own exact terms. `.sc-estimate`
  // (v2.13.0 §4h) says which is which, and the word is in the markup.
  const basis = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll('#saved .ss-saved__facts > div'));
    const mark = (name) => {
      const row = rows.find((r) => r.querySelector('dt').textContent.trim() === name);
      if (!row) return null;
      const dd = row.querySelector('dd');
      return { words: dd.textContent.trim(), estimate: !!dd.querySelector('.sc-estimate') };
    };
    return { aim: mark('aim'), trigger: mark('trigger'), limit: mark('limit'), stop: mark('stop') };
  });
  check('the aim is marked as derived, and says what from',
    !!basis.aim && basis.aim.estimate && basis.aim.words.includes('estimated from the indicative entry'), JSON.stringify(basis));
  check('and the ticket’s own terms beside it are never made approximate',
    ['trigger', 'limit', 'stop'].every((k) => basis[k] && !basis[k].estimate), JSON.stringify(basis));
  eq('a chart drawn from the saved bars', await attr(page, '#saved [data-panel="saved"] .sc-chart--stock', 'data-ticker'), trade);
  eq('and it does not dispose the detail’s own', await page.evaluate(() => SCStock.liveCharts()), 2);
  const archived = await said(page, '#saved [data-archived-order]');
  check('the instruction from that record is shown as dated history',
    archived.includes(dateWords(full.run.session)) && /not an instruction for today/.test(archived), archived.slice(0, 260));
  eq('no order can be placed from the sheet', await count(page, '#saved [data-copy-order], #saved [data-order-json]'), 0);
  check('a symbol on no list tonight says so rather than offering another', (await said(page, '#saved [data-current-setup="none"]')).includes('no current setup'), await said(page, '#saved [data-current-setup="none"]'));
  const since = await said(page, '#saved [data-saved="since"]');
  check('the later observation is in its own section with its actual date', since.includes(usd(obsNext.c)) && since.includes(dateWords(obsNext.date)), since.slice(0, 200));
  check('overlapping public history does not claim the basis is unknown', !since.includes('nothing confirms'), since.slice(0, 400));
  eq('the card and the detail reconcile to the same observation count', await count(page, '#saved [data-obs-row]'), 1);
  await closeSaved(page); await page.waitForTimeout(280);

  // ---- a NEWER signal for the same ticker must not be substituted
  const savedAgain = (await readStore(page)).items.find((x) => x.ticker === again);
  eq('the setup saved for this symbol is the EARLIER signal', savedAgain.session, full.run.session);
  check('and tonight’s record carries a newer one for it', (next.bursts || []).some((b) => b.ticker === again), 'no newer signal to confuse it with');
  await openSaved(page, again);
  check('and the sheet offers the CURRENT setup as a separate, named thing',
    (await said(page, '#saved [data-current-setup]')).length > 0 || (await count(page, `#saved [data-current-setup="${again}"]`)) === 1, await said(page, '#saved .ss-saved__foot'));
  // the symbol IS in tonight's record, with a newer signal and newer bars, so
  // this is where a chart drawn from the record instead of from the saved copy
  // would show: the panel's own last bar must be the SAVED signal's
  {
    const head = await said(page, '#saved [data-panel="saved"] .ss-chart-panel__head');
    check('the saved chart is the copy this browser froze, not tonight’s bars',
      head.includes(dateWords(savedAgain.session)) && head.includes(usd(savedAgain.snapshot.close)), head.slice(0, 160));
    const tonight = next.bursts.find((b) => b.ticker === again);
    check('and tonight’s own last bar is NOT what it shows',
      tonight.series[tonight.series.length - 1].date !== savedAgain.session
        && !head.includes(usd(tonight.series[tonight.series.length - 1].c)), head.slice(0, 160));
  }
  await closeSaved(page); await page.waitForTimeout(250);

  // ---- a same-session revision, then an older record
  await rerender(page, revised, LATER_NOW);
  eq('a different close on a session already observed is a revision, not a new day',
    await obsOf(page, trade), [[obsRev.date, obsRev.c, revised.run.session, true, 'match']]);
  check('and the card marks it', (await cardOf(page, trade)).includes('revised'), await cardOf(page, trade));
  // An older record that carries a session ALREADY OBSERVED at a different
  // price. The `full` night alone proves nothing here: every bar it holds for
  // this symbol is at or before the signal, so the merge never reaches the
  // rule -- a check that passed because a different rule rejected.
  const late = JSON.parse(JSON.stringify(next));
  late.run.session = '2026-09-15';
  // its observation block and its open model plan still hold the 11 Sep bar at
  // the price the `next` run published; leaving either in would have this
  // later record re-publish a session the revision already corrected, which is
  // the revision rule and not the one under test
  delete late.observations.symbols[trade];
  late.open_plans = (late.open_plans || []).filter((p) => p.ticker !== trade);
  late.bursts.push(Object.assign({}, tradeRow, { series: [
    { date: '2026-09-14', o: 118, h: 119, l: 117, c: 118.5, v: 1e6 },
    { date: '2026-09-15', o: 119, h: 120, l: 118, c: 119.5, v: 1e6 }] }));
  await rerender(page, late, '2026-09-15T22:31:00Z');
  eq('a later record adds the sessions it carries', (await obsOf(page, trade)).map((r) => r[0]), [obsRev.date, '2026-09-14', '2026-09-15']);
  const stale = JSON.parse(JSON.stringify(late));
  stale.run.session = '2026-09-14';
  stale.bursts[stale.bursts.length - 1].series = [{ date: '2026-09-14', o: 118, h: 119, l: 117, c: 111.11, v: 1e6 }];
  await rerender(page, stale, '2026-09-14T22:31:00Z');
  eq('an older record cannot replace a session a newer one already priced',
    (await obsOf(page, trade)).map((r) => [r[0], r[1], r[2]]),
    [[obsRev.date, obsRev.c, revised.run.session], ['2026-09-14', 118.5, '2026-09-15'], ['2026-09-15', 119.5, '2026-09-15']]);
  await rerender(page, full, FRESH_NOW);
  eq('and a record from before the signal contributes nothing at all', (await obsOf(page, trade)).length, 3);
  eq('the card says the observation is newer than the record on screen', await attr(page, `#following .ss-followed[data-ticker="${trade}"]`, 'data-observed'), 'ahead');
  check('in words', (await cardOf(page, trade)).includes('newer than this record'), await cardOf(page, trade));
  eq('nothing followed reached the record', await page.evaluate(() => JSON.stringify([SCStock.data.scorecard, SCStock.data.trades, SCStock.data.cash_budget])), publicBefore);
  check('and nothing followed reached the URL', !/ZZZZ|reference|shares/.test(await hash(page)), await hash(page));
  eq('follow-through page errors', errors, []);
  if (shotsDir) {
    await page.evaluate(() => { document.documentElement.removeAttribute('data-theme'); });
    await rerender(page, next, NEXT_NOW);
    await go(page, '#/setups'); await page.locator('#following').screenshot({ path: path.join(shotsDir, 'following-through-1280.png') });
    await openSaved(page, trade);
    await page.locator('#saved').screenshot({ path: path.join(shotsDir, 'saved-setup-1280.png') });
    await closeSaved(page); await page.waitForTimeout(200);
  }
  await context.close();
  await checkFollowBasis(browser, base, full, next);
  await checkFollowContext(browser, base, full, next);
  await checkFollowStates(browser, base, full, next);
}

// The price basis, the observation bound, and the model plan's provenance:
// each asked of a record built for the question, because no pipeline fixture
// can carry a split or twenty-five sessions of one symbol.
async function checkFollowBasis(browser, base, full, next) {
  const trade = full.trades[0], tradeRow = full.bursts.find((b) => b.ticker === trade);
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
  await followFrom(page, trade);

  // A legacy latest-only observation has no overlapping session. Keep the
  // uncertainty protection separate from today's history-bearing fixtures.
  const noOverlap = JSON.parse(JSON.stringify(next));
  delete noOverlap.observations.symbols[trade].history;
  await rerender(page, noOverlap, '2026-09-11T22:31:00Z');
  eq('without an overlapping session the basis stays unknown', (await obsOf(page, trade))[0][4], 'unknown');
  await openSaved(page, trade);
  const unknown = await said(page, '#saved [data-saved="since"]');
  check('and the limitation is stated in full there', unknown.includes('nothing confirms'), unknown.slice(0, 400));
  await closeSaved(page);

  // a record that carries a session the saved bars also carry, priced the same
  const same = JSON.parse(JSON.stringify(next));
  same.bursts.push(Object.assign({}, tradeRow, { series: tradeRow.series.concat([{ date: next.run.session, o: 120, h: 121, l: 119, c: 120.5, v: 1e6 }]) }));
  await rerender(page, same, '2026-09-11T22:31:00Z');
  eq('a session recorded in both, priced the same, confirms the basis', (await obsOf(page, trade))[0][4], 'match');
  check('and the change is shown plainly', (await cardOf(page, trade)).includes(pctOf((120.5 / tradeRow.close - 1) * 100)) && !/basis not confirmed/.test(await cardOf(page, trade)), await cardOf(page, trade));

  // the same record with every earlier bar re-priced: a split, as the archive shows one
  const split = JSON.parse(JSON.stringify(same));
  split.bursts[split.bursts.length - 1].series = split.bursts[split.bursts.length - 1].series.map((b) => Object.assign({}, b, { o: b.o / 2, h: b.h / 2, l: b.l / 2, c: b.c / 2 }));
  split.run.session = '2026-09-14';
  split.observations.symbols[trade] = { date: '2026-09-14', o: 60, h: 61, l: 59, c: 60.2, v: 1e6, since: full.run.session };
  await rerender(page, split, '2026-09-14T22:31:00Z');
  const rows = await obsOf(page, trade);
  eq('a session already observed printing a different close reads as a re-priced archive', rows[rows.length - 1][4], 'adjusted');
  const adj = await said(page, `#following .ss-followed[data-ticker="${trade}"] [data-group="since"]`);
  check('and no change is shown across it', !/[−+]\d+\.\d%/.test(adj), adj);
  check('the limitation is disclosed instead', adj.includes('re-adjusted'), adj);
  check('while the price and its date still are', adj.includes(usd(60.2)) && adj.includes(dateWords('2026-09-14')), adj);

  // the bound, and the original beneath it
  const many = JSON.parse(JSON.stringify(next));
  const bars = [];
  for (let i = 1; i <= 30; i++) { const d = new Date(Date.UTC(2026, 8, 11)); d.setUTCDate(d.getUTCDate() + i); bars.push({ date: d.toISOString().slice(0, 10), o: 100 + i, h: 101 + i, l: 99 + i, c: 100 + i, v: 1e6 }); }
  many.run.session = bars[bars.length - 1].date;
  many.bursts.push(Object.assign({}, tradeRow, { series: bars }));
  await rerender(page, many, '2026-10-21T22:31:00Z');
  const kept = await obsOf(page, trade);
  eq('at most the newest OBSERVATION_MAX sessions are kept', [kept.length, kept[kept.length - 1][0]], [await page.evaluate(() => SCStock.follow.OBSERVATION_MAX), bars[bars.length - 1].date]);
  const item = (await readStore(page)).items.find((x) => x.ticker === trade);
  eq('and the original snapshot survives the bound untouched', [item.snapshot.close, item.snapshot.levels.stop, item.evidence.series.length],
    [tradeRow.close, tradeRow.plan.stop, tradeRow.series.length]);
  check('a session no record carried is simply absent, never filled in',
    kept.every((r) => bars.some((b) => b.date === r[0])) && !kept.some((r) => r[0] === '2026-09-19'), JSON.stringify(kept.slice(0, 3)));

  // the model plan: a ticker alone is not a signal
  const plans = JSON.parse(JSON.stringify(next));
  const mine = (plans.open_plans || []).find((p) => p.ticker === trade);
  check('the sequel keeps an open model plan for the followed signal', !!mine, 'no open plan to test with');
  await rerender(page, plans, '2026-09-11T22:31:00Z');
  await openSaved(page, trade);
  eq('a plan for the same session, kind and rules is attached to the setup', await count(page, '#saved [data-model-update="matched"]'), 1);
  await closeSaved(page); await page.waitForTimeout(220);
  const other = JSON.parse(JSON.stringify(plans));
  other.open_plans.forEach((p) => { if (p.ticker === trade) p.picked = '2026-08-03'; });
  await rerender(page, other, '2026-09-11T22:31:00Z');
  await openSaved(page, trade);
  eq('a plan picked on another session is shown apart, never as this one’s update', [await count(page, '#saved [data-model-update="matched"]'), await count(page, '#saved [data-model-update="apart"]')], [0, 1]);
  check('and says which signal it is for', (await said(page, '#saved [data-model-update="apart"]')).includes(dateWords('2026-08-03')), await said(page, '#saved [data-model-update="apart"]'));
  await closeSaved(page); await page.waitForTimeout(220);
  const rules = JSON.parse(JSON.stringify(plans));
  rules.app.rules_version = 'ffffffffffff';
  await rerender(page, rules, '2026-09-11T22:31:00Z');
  await openSaved(page, trade);
  eq('a plan written under different rules is shown apart too', [await count(page, '#saved [data-model-update="matched"]'), await count(page, '#saved [data-model-update="apart"]')], [0, 1]);
  check('naming both rule identities', (await said(page, '#saved [data-model-update="apart"]')).includes('ffffffff'), await said(page, '#saved [data-model-update="apart"]'));
  eq('basis page errors', errors, []);
  await context.close();
}

// The reader's place: opening a saved setup and coming back must leave the
// lens, the pins, the selection, the scroll and the focus exactly as they were.
async function checkFollowContext(browser, base, full, next) {
  const trade = full.trades[0];
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
  await followFrom(page, trade);
  const others = full.bursts.filter((b) => b.ticker !== trade).slice(0, 2).map((b) => b.ticker);
  for (const t of others) { await clickPick(page, t); await page.locator(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${t}"]) .ss-pin`).click(); await page.waitForTimeout(150); }
  await setLens(page, 'a');
  await clickPick(page, trade);
  const beforeState = { lens: await lensNow(page), hash: await hash(page), pins: await count(page, '#compare-tray .ss-tray__pin') };
  eq('the return-context check starts with two actual pins', beforeState.pins, 2);
  // The saved destination owns the sheet's return route.
  await go(page, '#/setups'); beforeState.hash = '#/setups';
  await page.locator(`#following .ss-followed[data-ticker="${trade}"] [data-open-saved]`).scrollIntoViewIfNeeded();
  await page.waitForTimeout(200);
  const scrollBefore = await page.evaluate(() => window.pageYOffset);
  check('the saved destination is visible', await page.locator('#view-setups').isVisible());
  await page.locator(`#following .ss-followed[data-ticker="${trade}"] [data-open-saved]`).click();
  await page.waitForTimeout(380);
  eq('the sheet is over the page, not instead of it', [await count(page, '#saved[open]'), await visibleView(page)], [1, ['view-setups']]);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  eq('Escape puts the reader back on the route they came from', await hash(page), beforeState.hash);
  eq('with the same lens', await lensNow(page), beforeState.lens);
  eq('the same pins', await count(page, '#compare-tray .ss-tray__pin'), beforeState.pins);
  check('and the same scroll', Math.abs((await page.evaluate(() => window.pageYOffset)) - scrollBefore) < 40, `${await page.evaluate(() => window.pageYOffset)} vs ${scrollBefore}`);
  eq('focus is back on the control that opened it', await page.evaluate(() => (document.activeElement && document.activeElement.dataset.openSaved) || '(none)'), `burst:${trade}:${full.run.session}:${full.app.rules_version}`);
  // a saved setup the lens hides is still reachable by its own route
  await rerender(page, next, '2026-09-11T22:31:00Z');
  await page.evaluate(() => { location.hash = '#/explore'; }); await page.waitForTimeout(200);
  await go(page, '#/followed/' + encodeURIComponent(`burst:${trade}:${full.run.session}:${full.app.rules_version}`));
  await page.waitForTimeout(350);
  eq('a deep link opens the saved setup even when the symbol is in no list', [await count(page, '#saved[open]'), await savedTitle(page)], [1, trade]);
  await closeSaved(page); await page.waitForTimeout(300);
  check('and closing it leaves a route the page can show', /^#\/explore/.test(await hash(page)), await hash(page));
  eq('context page errors', errors, []);
  await context.close();
}

// The states a saved setup has to survive that no single page can show: a
// second tab writing the same store, a store too full for the chart, the
// keyboard alone, and the phone.
async function checkFollowStates(browser, base, full, next) {
  const trade = full.trades[0], other = full.bursts.find((b) => b.ticker !== trade).ticker;

  // --- two tabs, one origin -------------------------------------------
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'dark' });
  const twoErrors = [];
  await ctx.addInitScript(({ dataUrl, now }) => {
    window.SCStock = { dataUrl, now };
    try { localStorage.setItem('spicystock:lens:v1', JSON.stringify({ bursts: 'all', 'setting-up': 'all', sort: null })); } catch (e) { /* none */ }
  }, { dataUrl: '/tests/fixtures/page/full.json', now: FRESH_NOW });
  const a = await ctx.newPage(), b = await ctx.newPage();
  a.on('pageerror', (e) => twoErrors.push('a: ' + e.message));
  b.on('pageerror', (e) => twoErrors.push('b: ' + e.message));
  for (const p of [a, b]) {
    await p.goto(base + `/docs/index.html#/explore/bursts/${trade}`, { waitUntil: 'load' });
    await p.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
  }
  await a.click('#detail .ss-follow button[data-follow-action="add"]'); await a.waitForTimeout(250);
  await b.waitForTimeout(400);
  eq('a follow in one tab shows in the other without a reload', await count(b, '#following .ss-followed'), 1);
  // the second tab follows something else; the first must not write its stale list back
  await go(b, `#/explore/bursts/${other}`);
  await b.click('#detail .ss-follow button[data-follow-action="add"]'); await b.waitForTimeout(300);
  await a.click('#detail .ss-follow button[data-follow-action="edit"]');
  await a.fill('#detail .ss-follow__form input', '9');
  await a.click('#detail .ss-follow__form button[type="submit"]'); await a.waitForTimeout(300);
  const both = await a.evaluate((k) => JSON.parse(localStorage.getItem(k)).items.map((x) => [x.ticker, x.reference_shares]), FOLLOW_KEY);
  eq('an edit in one tab keeps the other tab’s follow', both.length, 2);
  eq('and applies to its own', both.find((r) => r[0] === trade)[1], 9);
  eq('two-tab page errors', twoErrors, []);
  await ctx.close();

  // --- a store with no room for the chart -------------------------------
  {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
    // refuse any write over a few kilobytes, which is a quota as a browser reports one
    await page.evaluate(() => {
      window.__setItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k, v) {
        if (/following/.test(k) && String(v).length > 4000) { const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e; }
        return window.__setItem.call(this, k, v);
      };
    });
    await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(300);
    eq('a store with no room still saves the setup', await attr(page, '#detail .ss-follow', 'data-follow'), 'following');
    eq('without its chart', await page.evaluate((k) => JSON.parse(localStorage.getItem(k)).items[0].evidence, FOLLOW_KEY), null);
    await openSaved(page, trade);
    check('and the sheet says so rather than drawing one from tonight',
      (await said(page, '#saved [data-chart="unsaved"]')).includes('Original chart was not saved'), await said(page, '#saved [data-chart="unsaved"]'));
    await page.evaluate(() => { Storage.prototype.setItem = window.__setItem; });
    eq('full-store page errors', errors, []);
    await context.close();
  }

  // --- the keyboard alone, and the phone --------------------------------
  {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { lens: 'all', height: 844, hash: `#/explore/bursts/${trade}` });
    await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(250);
    await rerender(page, next, '2026-09-11T22:31:00Z');
    await go(page, '#/setups');
    eq('the phone stacks the shelf full-width', await page.locator('#following .ss-followed').first().evaluate((n) => Math.round(n.getBoundingClientRect().width) > window.innerWidth * 0.75), true);
    eq('and nothing scrolls sideways', await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
    // reach the saved setup by keyboard only
    await go(page, "#/setups");
    await page.locator(`#following .ss-followed[data-ticker="${trade}"] [data-open-saved]`).focus();
    await page.keyboard.press('Enter'); await page.waitForTimeout(400);
    eq('Enter on the card’s button opens the saved setup', [await count(page, '#saved[open]'), await savedTitle(page)], [1, trade]);
    check('and the focus is inside the sheet', await page.evaluate(() => !!document.activeElement.closest('#saved')), await active(page));
    await page.keyboard.press('Escape'); await page.waitForTimeout(400);
    eq('Escape closes it', await count(page, '#saved[open]'), 0);
    eq('phone sideways after the sheet', await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
    if (shotsDir) { await go(page, '#/setups'); await page.locator('#following').screenshot({ path: path.join(shotsDir, 'following-through-390.png') }); }
    eq('phone follow-through page errors', errors, []);
    await context.close();
  }

  // --- a reference size the reader set survives an observation -----------
  {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${trade}` });
    await page.click('#detail .ss-follow button[data-follow-action="add"]'); await page.waitForTimeout(220);
    await page.click('#detail .ss-follow button[data-follow-action="edit"]');
    await page.fill('#detail .ss-follow__form input', '17');
    await page.click('#detail .ss-follow__form button[type="submit"]'); await page.waitForTimeout(260);
    await rerender(page, next, '2026-09-11T22:31:00Z');
    eq('a reference size survives the observations that arrive after it',
      await page.evaluate((k) => JSON.parse(localStorage.getItem(k)).items[0].reference_shares, FOLLOW_KEY), 17);
    check('and is still labelled as the reader’s', (await cardOf(page, trade)).includes('your reference size 17 shares'), await cardOf(page, trade));
    eq('states page errors', errors, []);
    await context.close();
  }
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
    check(`${name}: the card, the detail line and the scan table say the ratio is missing`, r.card.includes('vol —') && r.sub.includes('on —× prior-session volume') && r.table.includes('—× vol'), [r.card, r.sub, r.table]);
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
    check('a zero ratio prints as 0.0×, never as missing', r.card.includes('vol 0.0×') && r.sub.includes('on 0.0× prior-session volume') && r.table.includes('0.0× vol') && r.facts.includes('0.0× volume') && !r.facts.includes('not recorded') && !r.facts.includes('read from the checklist'), [r.card, r.sub, r.table]);
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
    check('the card and the detail line print the row’s own ratio', r.card.includes('vol ' + own.toFixed(1) + '×') && r.sub.includes('on ' + own.toFixed(1) + '× prior-session volume'), [r.card, r.sub]);
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
    const listed = await page.locator('.sc-pick__item').evaluateAll((els) => els.map((e) => e.dataset.ticker));
    check(`${label}: both stocks under the finger are offered, not just the topmost`, listed.includes(A) && listed.includes(B), JSON.stringify({ listed, topmost }));
    check(`${label}: the panel says how many are under the finger and that none is chosen`, (await text(page, '.sc-pick h4')).includes('within a finger') && (await text(page, '.sc-pick__hint')).includes('None is chosen'), await text(page, '.sc-pick'));
    eq(`${label}: the first item takes the focus`, await page.evaluate(() => document.activeElement.dataset.ticker), listed[0]);
    // The panel IS the design system's `.sc-pick` (v2.13.0 §4f) and not a local
    // look-alike: its item is the 44px the release asks a finger for, it names
    // the stock in `__name`, what else is known in `__meta`, and the map's own
    // vertical value in the released `.sc-figure` slot.
    eq(`${label}: nothing of the local chooser's own classes is left`, await count(page, '.ss-map__nearby, .ss-map__nearby-item, .ss-map__nearby-hint, .ss-map__nearby-measures, .ss-map__nearby-grade'), 0);
    const shape = await page.locator('.sc-pick__item').evaluateAll((els) => els.map((e) => ({
      t: e.dataset.ticker, h: Math.round(e.getBoundingClientRect().height),
      minH: getComputedStyle(e).minHeight,
      name: (e.querySelector('.sc-pick__name') || {}).textContent || null,
      meta: (e.querySelector('.sc-pick__meta') || {}).textContent || null,
      figure: (e.querySelector('.sc-figure') || {}).textContent || null,
      spoken: e.getAttribute('aria-label') || '' })));
    check(`${label}: the item declares the 44px the release asks a finger for`,
      shape.length > 1 && shape.every((s) => s.minH === '44px'), JSON.stringify(shape.map((s) => [s.t, s.minH])));
    check(`${label}: and is drawn at least that tall`,
      shape.every((s) => s.h >= 44), JSON.stringify(shape.map((s) => [s.t, s.h])));
    check(`${label}: each item fills the released name, meta and figure slots`,
      shape.every((s) => s.name === s.t && /volume/.test(s.meta || '') && /^[+−]?\d+(\.\d)?%$/.test(s.figure || '')), JSON.stringify(shape));
    check(`${label}: and is spoken as one sentence, so the grid's order cannot mislead`,
      shape.every((s) => s.spoken.startsWith(s.t + ':') && s.spoken.includes('volume')), JSON.stringify(shape.map((s) => s.spoken)));
    // The release sizes `.sc-pick` against its host and expects the host to let
    // it overflow; THIS host clips (`.ss-map { overflow: hidden }`), so the
    // panel has to fit inside the pane and carry its own scroll. A max-height
    // that outgrew the pane would cut the last option off with nothing saying so.
    const fit = await page.evaluate(() => {
      const node = document.querySelector('.sc-pick');
      const pane = document.querySelector('#burst-map .ss-map__surface').getBoundingClientRect();
      const box = node.getBoundingClientRect();
      return { inside: box.top >= pane.top - 1 && box.bottom <= pane.bottom + 1 && box.left >= pane.left - 1 && box.right <= pane.right + 1,
               scrollable: getComputedStyle(node).overflowY === 'auto',
               pane: Math.round(pane.height), panel: Math.round(box.height),
               clipped: node.scrollHeight > node.clientHeight + 1 };
    });
    check(`${label}: the panel fits the pane its host clips, and scrolls rather than cutting an option off`,
      fit.inside && fit.scrollable, JSON.stringify(fit));
    // Escape closes it and chooses nothing
    await page.keyboard.press('Escape'); await page.waitForTimeout(150);
    eq(`${label}: Escape closes the chooser without choosing`, [await page.getAttribute('#burst-map', 'data-nearby'), await page.getAttribute('#burst-map', 'data-selected')], ['closed', before]);
    // the stock the finger was on, chosen by name, reaches every view of it
    await tap(a.cx, a.cy); await page.waitForTimeout(250);
    await page.click(`.sc-pick__item[data-ticker="${A}"]`); await page.waitForTimeout(300);
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
    // The panel OPEN, which no shot ever caught: the component has to be LOOKED
    // at. It goes here and not beside the crowded tap because an element
    // screenshot scrolls its element into view, which moves the viewport out
    // from under the tap coordinates measured before it -- everything after
    // this point is driven by focus, not by coordinates.
    if (shotsDir) await page.locator('#burst-map').screenshot({ path: path.join(shotsDir, `map-pick-open-${label}.png`) });
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
    const panels = () => count(page, '.sc-pick');
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
      const q = document.querySelector('.sc-pick');
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
    eq('the chooser does not claim a modality the page does not have', await page.getAttribute('.sc-pick', 'aria-modal'), null);
    eq('it is a labelled dialog all the same', [await page.getAttribute('.sc-pick', 'role'), await page.locator('.sc-pick').getAttribute('aria-labelledby')], ['dialog', 'ss-map-nearby-h']);
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
  check('the empty following lens explains itself', (await text(f.page, '#pick-list [data-empty="lens"]')).includes('My setups'), await text(f.page, '#pick-list [data-empty="lens"]'));
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
  eq('the side without browser bars offers its retained source without inventing a chart', [await count(nb.page, '#compare [data-side="b"] [data-load-chart]'), await count(nb.page, '#compare [data-side="b"] .sc-chart--stock')], [1, 0]);
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

  // A value the record never supplied wears the design system's `.sc-unreported`
  // (v2.13.0 §4h): the WORDS stay -- the mark is reinforcement, not the meaning
  // -- but it must not align with, weigh like, or be mistaken for a measurement
  // sitting in the same column. Every compared field is present in the fixture,
  // so one is dropped here to make the case exist at all.
  const missing = JSON.parse(JSON.stringify(data));
  delete missing.bursts[0].gain_pct;
  const missPath = '/tests/fixtures/page/.compare-missing.json';
  await writeFile(path.join(ROOT, missPath), JSON.stringify(missing));
  try {
    const u = await open(browser, base, missPath, FRESH_NOW, 1280, { lens: 'all' });
    await u.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${A.ticker}"]) .ss-pin`);
    await u.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${B.ticker}"]) .ss-pin`); await u.page.waitForTimeout(200);
    await u.page.click('#compare-open'); await u.page.waitForTimeout(600);
    const cells = await u.page.locator('#compare-table tbody td').evaluateAll((els) => els.map((e) => {
      const span = e.querySelector('.sc-unreported');
      return { missing: e.hasAttribute('data-missing'), words: e.textContent.trim(), wrapped: !!span,
               cellFont: getComputedStyle(e).fontFamily, valueFont: getComputedStyle(span || e).fontFamily };
    }));
    const absent = cells.filter((c) => c.missing), present = cells.filter((c) => !c.missing);
    check('a compared value the record never supplied exists to be marked', absent.length >= 1,
      JSON.stringify(cells.map((c) => [c.missing, c.words.slice(0, 24)])));
    check('and it says so in words, inside .sc-unreported',
      absent.every((c) => c.wrapped && c.words === 'not recorded'), JSON.stringify(absent));
    check('and it is set as an absence rather than as a figure',
      absent.every((c) => c.valueFont !== c.cellFont), JSON.stringify(absent.map((c) => [c.cellFont, c.valueFont])));
    check('a value the record DID supply is neither marked nor wrapped',
      present.length > 1 && present.every((c) => !c.wrapped), JSON.stringify(present.slice(0, 3)));
    eq('missing-value comparison page errors', u.errors, []);
    await u.context.close();
  } finally { await unlink(path.join(ROOT, missPath)); }
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
  await page.locator('#detail .ss-evidence__check details > summary').first().click();
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
  const tileTag = (want) => page.locator('#detail .ss-checks [data-check]').evaluateAll((e, w) => e.filter((x) => !!x.querySelector('[data-check-action]') === w).map((x) => x.dataset.check).sort(), want);
  eq('exactly the checks the record dates are ways onto the chart', await tileTag(true), ['close_near_high', 'consolidation', 'narrow_or_negative', 'range_expansion', 'volume']);
  eq('and every undated one stays a tile', await tileTag(false), ['linearity', 'two_days', 'young_trend']);
  await page.click('#detail .ss-checks [data-check-action="consolidation"]'); await page.waitForTimeout(350);
  eq('the tile marks the base through the one mechanism', await markOf(page), `${b.quality.base.start}/${b.quality.base.end}`);
  eq('and the evidence control shows as pressed', await page.locator('#detail .ss-evidence [data-anchor="base"]').getAttribute('aria-pressed'), 'true');
  await page.click('#detail .ss-checks [data-check-action="volume"]'); await page.waitForTimeout(300);
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

// ---------------------------------------------------------------- reaching past the lens
// visible(stage) is the page's ONE visible-candidate selector, and the cards,
// the map, the counts and the stepper all read it. But three controls reach a
// stock from outside that list: the chooser, which is every stock in the
// record by design; the comparison tray, whose pins outlive a lens change; and
// the map, which had no way to pin at all. Each is read here against the
// RECORD's own grades, never against the page's answer.
async function checkReach(browser, base, data) {
  console.log('-- the lens, where the reader reaches past it');
  const aQuality = data.bursts.filter((b) => TRADE_GRADES.includes(b.grade)).map((b) => b.ticker);
  const all = data.bursts.map((b) => b.ticker);
  const outside = all.filter((t) => !aQuality.includes(t));
  const coils = data.watchlist.top.map((c) => c.ticker);
  check('the fixture can tell the lens apart from the record', outside.length > 0 && aQuality.length > 0, `${aQuality.length} A-quality, ${outside.length} outside`);

  // ---- the chooser, at the width that offers it
  const ch = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844, lens: 'a' });
  await ch.page.click('#choose-open'); await ch.page.waitForTimeout(250);
  const itemsIn = () => ch.page.locator('#chooser-list .ss-chooser__item[data-in-lens="true"] b').evaluateAll((e) => e.map((x) => x.textContent));
  const itemsOut = () => ch.page.locator('#chooser-list .ss-chooser__item[data-in-lens="false"] b').evaluateAll((e) => e.map((x) => x.textContent));
  eq('the chooser marks the stocks the lens holds', await itemsIn(), aQuality.concat(coils));
  eq('and marks the ones it hides, rather than listing them alike', await itemsOut(), outside);
  eq('every stock in the record is still reachable', await count(ch.page, '#chooser-list .ss-chooser__item'), all.length + coils.length);
  eq('the in-lens group comes first, so Enter chooses a stock the reader can see',
    await ch.page.locator('#chooser-list .ss-chooser__item').first().getAttribute('data-in-lens'), 'true');
  check('the status line says how many are outside the lens BEFORE one is chosen',
    (await text(ch.page, '#chooser-status')).includes(`${outside.length} of them outside the lens you are reading`), await text(ch.page, '#chooser-status'));
  check('the outside group says what choosing one will do',
    (await said(ch.page, '#chooser-list .ss-chooser__why')).includes('your A-quality lens is not changed for next time'), await said(ch.page, '#chooser-list .ss-chooser__why'));
  eq('the group headings count each side', await ch.page.locator('#chooser-list .ss-chooser__group').evaluateAll((e) => e.map((x) => x.textContent)),
    [`bursts · ${aQuality.length} in the A-quality lens`, `bursts · ${outside.length} outside it`, `setting up · ${coils.length}`]);
  // choosing one outside still works, still says so, and still does not store the widening
  await tap(ch.page, `#chooser-list .ss-chooser__item[data-id="bursts:${outside[0]}"]`, 'a stock outside the lens is still choosable');
  await ch.page.waitForTimeout(150);
  eq('choosing a hidden stock opens it', await said(ch.page, '#detail-h2'), outside[0]);
  check('and the page says the lens was widened for it', (await text(ch.page, '#picks-status')).includes(`${outside[0]} is outside the A-quality lens`), await text(ch.page, '#picks-status'));
  eq('the reader\'s own stored lens is untouched by that widening',
    await ch.page.evaluate(() => JSON.parse(localStorage.getItem('spicystock:lens:v1') || '{}').bursts), 'a');
  // an unnarrowed lens hides nothing, so the chooser says nothing about one
  eq('no chooser check left the page in error', ch.errors, []);
  await ch.context.close();

  const wide = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 390, { height: 844, lens: 'all' });
  await wide.page.click('#choose-open'); await wide.page.waitForTimeout(250);
  eq('a lens that hides nothing adds no second group', await count(wide.page, '#chooser-list [data-group="outside"]'), 0);
  eq('and marks nothing as outside it', await count(wide.page, '#chooser-list .ss-chooser__item[data-in-lens="false"]'), 0);
  check('nor mentions a lens in the count', !(await text(wide.page, '#chooser-status')).includes('outside the lens'), await text(wide.page, '#chooser-status'));
  eq('no wide-lens chooser errors', wide.errors, []);
  await wide.context.close();

  // ---- the tray: a pin outlives a lens change, and says so
  const tr = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all' });
  await tr.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${outside[0]}"]) .ss-pin`); await tr.page.waitForTimeout(200);
  await tr.page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${aQuality[0]}"]) .ss-pin`); await tr.page.waitForTimeout(200);
  eq('both are pinned under the wide lens', await tr.page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [outside[0], aQuality[0]]);
  eq('and neither is marked, because the lens hides neither', await count(tr.page, '#compare-tray .ss-tray__pin[data-hidden-by]'), 0);
  await setLens(tr.page, 'a');
  eq('narrowing the lens drops no pin', await tr.page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [outside[0], aQuality[0]]);
  eq('the pin the lens now hides is the one marked', await tr.page.locator('#compare-tray .ss-tray__pin[data-hidden-by]').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [outside[0]]);
  check('the chip itself names the lens that hides it', (await said(tr.page, `#compare-tray .ss-tray__pin[data-ticker="${outside[0]}"]`)).includes('outside the A-quality lens'),
    await said(tr.page, `#compare-tray .ss-tray__pin[data-ticker="${outside[0]}"]`));
  check('and the tray says it stays pinned and why the comparison still holds it',
    (await said(tr.page, '#compare-tray .ss-tray__away')).includes('not in the list behind this') && (await said(tr.page, '#compare-tray .ss-tray__away')).includes('reads the record, not the lens'),
    await said(tr.page, '#compare-tray .ss-tray__away'));
  eq('the note names the hidden pin and only it', await tr.page.locator('#compare-tray .ss-tray__away [data-tray-show]').evaluateAll((e) => e.map((x) => x.dataset.trayShow)), [outside[0]]);
  check('and does not name the pin the lens still shows', !(await said(tr.page, '#compare-tray .ss-tray__away')).includes(aQuality[0]), await said(tr.page, '#compare-tray .ss-tray__away'));
  eq('the comparison is still offered over the pair', await tr.page.locator('#compare-open').isDisabled(), false);
  // The tray is redrawn WITH the list, and the list is redrawn on every
  // keystroke -- so it must be redrawn only when what it shows has changed.
  // A rebuild under the reader drops whatever they had focused in it onto
  // <body>; the re-rendered PROMPT would look identical, so the focus is
  // what this reads. The query is dispatched without touching the search
  // box, because focusing it would move the focus by itself.
  const typeSearch = (q) => tr.page.evaluate((q) => { const i = document.getElementById('search'); i.value = q; i.dispatchEvent(new Event('input', { bubbles: true })); }, q);
  await tr.page.focus('#compare-tray [data-tray-clear]');
  await typeSearch(aQuality[0].slice(0, 1)); await tr.page.waitForTimeout(250);
  eq('a keystroke in the search does not drop the focus held in the tray',
    await tr.page.evaluate(() => !!(document.activeElement && document.activeElement.hasAttribute && document.activeElement.hasAttribute('data-tray-clear'))), true);
  await typeSearch(''); await tr.page.waitForTimeout(200);
  eq('and the tray still holds the pair after it', await tr.page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [outside[0], aQuality[0]]);
  await tap(tr.page, `#compare-tray [data-tray-show="${outside[0]}"]`, 'the tray offers one click to the hidden pin');
  await tr.page.waitForTimeout(150);
  eq('one click reaches the hidden pin', await said(tr.page, '#detail-h2'), outside[0]);
  eq('no tray errors', tr.errors, []);
  await tr.context.close();

  // ---- the map: the same Compare toggle, where the reader is already reading
  const mp = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280, { lens: 'all' });
  await mp.page.click('#discover .sc-tab[data-discover="map"]'); await mp.page.waitForTimeout(350);
  eq('the map table carries a compare column', await mp.page.locator('#burst-map .ss-map__table thead th').evaluateAll((e) => e.map((x) => x.textContent)),
    ['burst', 'gain', 'volume vs prev', 'grade', 'rank', 'source', 'plotted', 'compare']);
  eq('every mapped burst has one', await count(mp.page, '#burst-map .ss-map__table .ss-pin'), all.length);
  await openAll(mp.page, '#burst-map .ss-map__table'); await mp.page.waitForTimeout(150);
  await mp.page.click(`#burst-map .ss-map__point[data-ticker="${all[1]}"]`); await mp.page.waitForTimeout(300);
  eq('the chosen point carries one beside its measurements', await attr(mp.page, '#burst-map .ss-map__control .ss-pin', 'data-ticker'), all[1]);
  await tap(mp.page, '#burst-map .ss-map__control .ss-pin', 'the chosen point\'s toggle can be used');
  await tap(mp.page, `#burst-map .ss-map__table .ss-pin[data-ticker="${all[3]}"]`, 'a table row\'s toggle can be used');
  eq('two can be pinned without leaving the map', await mp.page.locator('#compare-tray .ss-tray__pin').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [all[1], all[3]]);
  // one mechanism, not two: the card's own toggle reads the pin the map made
  eq('the map\'s pin IS the card\'s pin', await attr(mp.page, `#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${all[1]}"]) .ss-pin`, 'aria-pressed'), 'true');
  eq('and the map\'s own copies agree with it', await attr(mp.page, `#burst-map .ss-map__table .ss-pin[data-ticker="${all[1]}"]`, 'aria-pressed'), 'true');
  const beforeMap = await hash(mp.page);
  await tap(mp.page, `#burst-map .ss-map__table .ss-pin[data-ticker="${all[5]}"]`, 'a third can be offered from the map');
  eq('pinning from the map navigates nowhere', await hash(mp.page), beforeMap);
  eq('and a third still asks which to replace', await attr(mp.page, '#compare-tray .ss-tray__ask', 'data-ask'), 'replace');
  await tap(mp.page, '#compare-tray [data-ask-action="cancel"]', 'the third can be declined from the map');
  await tap(mp.page, '#compare-open', 'the comparison opens from the map');
  await mp.page.waitForTimeout(600);
  eq('the sheet opens over the pair pinned on the map', await mp.page.locator('#compare .ss-compare__side').evaluateAll((e) => e.map((x) => x.dataset.ticker)), [all[1], all[3]]);
  eq('each side keeps its own namespaced panel', await mp.page.locator('#compare .ss-chart-panel').evaluateAll((e) => e.map((x) => x.dataset.panel)), ['cmp-a', 'cmp-b']);
  eq('with two live charts, as from the cards', await mp.page.evaluate(() => window.SCStock.liveCharts()), 3);
  eq('no map-compare errors', mp.errors, []);
  await mp.context.close();
}

// ---------------------------------------------------------------------------
// The session-aware desk: which session the plans are for, whether its entry
// window is still applicable, and loading a newer record without taking the
// reader's place with it.
//
// The clock is INJECTED at every instant here (SCStock.render(data, when)), so
// no check in this suite depends on the hour it runs -- this repository's worst
// shape of unfailable test. Every instant is stated in market time beside its
// UTC, because a reader of this file has to be able to check the arithmetic.
// ---------------------------------------------------------------------------

// September 2026 is EDT, UTC-4. `next.json` is measured on Friday 11 Sep and
// its plans are for Monday 14 Sep, whose window is 9:30-10:00 AM ET.
const WHEN = {
  evening: ['2026-09-11T22:31:00Z', 'Fri 11 Sep 6:31 PM ET, the evening it published'],
  saturday: ['2026-09-12T13:45:00Z', 'Sat 12 Sep 9:45 AM ET, the window\'s clock time on a weekend'],
  sunday: ['2026-09-13T18:00:00Z', 'Sun 13 Sep 2:00 PM ET'],
  before: ['2026-09-14T13:00:00Z', 'Mon 14 Sep 9:00 AM ET, before the open'],
  ready: ['2026-09-14T13:28:00Z', 'Mon 14 Sep 9:28 AM ET, the preparation reminder'],
  bell: ['2026-09-14T13:30:00Z', 'Mon 14 Sep 9:30 AM ET, the bell'],
  inside: ['2026-09-14T13:40:00Z', 'Mon 14 Sep 9:40 AM ET, inside the window'],
  last: ['2026-09-14T13:59:59Z', 'Mon 14 Sep 9:59:59 AM ET, its last second'],
  cutoff: ['2026-09-14T14:00:00Z', 'Mon 14 Sep 10:00 AM ET, the cutoff itself'],
  after: ['2026-09-14T15:00:00Z', 'Mon 14 Sep 11:00 AM ET, the acceptance instant'],
  evening2: ['2026-09-14T21:00:00Z', 'Mon 14 Sep 5:00 PM ET, after the close'],
};
// an instant on a record's OWN applicable session at a market-clock time,
// built from the offset the record carries rather than from arithmetic here
const atSession = (tm, hhmm) => new Date(`${tm.applicable_session}T${hhmm}:00${tm.opens_at.slice(-6)}`).toISOString();
const phaseAt = (page, data, key) => page.evaluate(([d, at]) => {
  window.SCStock.render(d, new Date(at));
  const a = window.SCStock.avail;
  return { phase: a.phase, offered: a.offered, lead: a.lead, pub: a.pub.state, reason: a.reason };
}, [data, WHEN[key][0]]);

async function checkSession(browser, base, full) {
  console.log('-- session: which session the plans are for, and whether its window is still open');
  const next = JSON.parse(await readFile(path.join(FIXTURES, 'next.json'), 'utf8'));
  const revised = JSON.parse(await readFile(path.join(FIXTURES, 'revised.json'), 'utf8'));
  const closed = JSON.parse(await readFile(path.join(FIXTURES, 'closed.json'), 'utf8'));
  const red = JSON.parse(await readFile(path.join(FIXTURES, 'red.json'), 'utf8'));
  const tm = next.run.timing, forDay = dateWords(tm.applicable_session);
  const order = next.trades.find((t) => { const b = next.bursts.find((x) => x.ticker === t); return b && b.plan && b.plan.order_json; });
  check('the fixture this suite needs carries a ticket for a named session', !!order && !!tm, `${order} for ${tm && tm.applicable_session}`);
  eq('and the applicable session is the weekday after the measured one', [tm.measured_session, tm.applicable_session], ['2026-09-11', '2026-09-14']);

  // ---- the phase at every boundary, on one page, the clock moved under it
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/next.json', WHEN.evening[0], 1280,
    { lens: 'all', hash: `#/explore/bursts/${order}` });
  const want = { evening: 'upcoming', saturday: 'upcoming', sunday: 'upcoming', before: 'upcoming', ready: 'upcoming',
    bell: 'open', inside: 'open', last: 'open', cutoff: 'ended', after: 'ended', evening2: 'ended' };
  // by evening2 the record IS a session behind (the next run has not landed),
  // so publication refuses there too: the one instant where both do
  const pubWant = { evening2: 'pending', saturday: 'closed', sunday: 'closed' };
  for (const key of Object.keys(want)) {
    const got = await phaseAt(page, next, key);
    eq(`${WHEN[key][1]} -> the window is ${want[key]}`, got.phase, want[key]);
    eq(`  and an order is ${want[key] === 'ended' ? 'not ' : ''}offered there`, got.offered, want[key] !== 'ended');
    eq(`  publication at ${key}`, got.pub, pubWant[key] || 'fresh');
  }
  eq('at the one instant where both refuse, publication is the reason given',
    (await phaseAt(page, next, 'evening2')).lead, 'not offered');
  // the weekend cases are the ones a naive "is it 9:45 yet" would get wrong:
  // Saturday at 9:45 AM ET is inside the window's CLOCK TIME and is not a session
  check('a weekend at the window\'s own clock time is still upcoming, not open',
    (await phaseAt(page, next, 'saturday')).phase === 'upcoming', 'a Saturday read as an open window');

  // ---- THE ACCEPTANCE: the 11:00 AM page no longer names a passed deadline
  await phaseAt(page, next, 'after');
  const nextH3 = await text(page, '#next-h3'), nextP = await text(page, '#next-p');
  check('at 11:00 AM the next action does NOT tell the reader to act before 9:28 AM',
    !/before 9:28/.test(nextH3 + ' ' + nextP), `${nextH3} | ${nextP}`);
  check('it says the window for that named session has ended',
    nextH3 === `The entry window for ${forDay} has ended.`, nextH3);
  check('and it never says "tomorrow" of the day it is on', !/tomorrow/i.test(nextH3 + ' ' + nextP), `${nextH3} | ${nextP}`);
  check('the cancellation is conditional and claims nothing was cancelled for the reader',
    /If you submitted an order that did not fill/.test(nextP) && /places nothing and cancels nothing/.test(nextP), nextP);

  // ---- the compact area tells the two facts apart
  eq('the market area has one line for the data and one for the plan',
    await page.locator('#market-facts > div').evaluateAll((e) => e.map((x) => x.dataset.fact)), ['data', 'plan']);
  check('with the regime beside the verdict it belongs to', !!(await count(page, '#cover-regime .sc-chip')), 'no regime chip on the verdict');
  const dataLine = await said(page, '#market-facts [data-fact="data"]'), planLine = await said(page, '#market-facts [data-fact="plan"]');
  check('the data line names the measured session and the publication time',
    dataLine.includes(dateWords(next.run.session)) && /published \d+:\d\d [AP]M ET/.test(dataLine), dataLine);
  check('and carries the freshness chip, which covers it and nothing else', dataLine.includes('fresh'), dataLine);
  check('the plan line names the applicable session and the window',
    planLine.includes(forDay) && planLine.includes('9:30–10:00 AM ET'), planLine);
  check('and its own chip says the window ended, beside a fresh data line',
    planLine.includes('entry window ended'), planLine);
  check('so no single green chip can be read as covering both', !/fresh/.test(planLine), planLine);

  // ---- every action surface, at the same instant
  const bar = await said(page, '.ss-action');
  eq('the stock action bar is marked with the window it is in', await attr(page, '.ss-action', 'data-window'), 'ended');
  check('it gives the reason and keeps the setup readable',
    bar.includes(`entry window for ${forDay} ended`) && /stay readable/.test(bar), bar);
  check('its button inspects the recorded ticket rather than offering it',
    (await said(page, '.ss-action [data-open]')).includes('Inspect recorded plan'), await said(page, '.ss-action [data-open]'));
  await openAll(page, '#disc-plan');
  eq('the plan disclosure offers no copy control', await count(page, '#disc-plan [data-copy]'), 0);
  eq('and prints what the record published, as history', await count(page, '#disc-plan [data-recorded-ticket]'), 1);
  check('marked as history and not as an order to place',
    (await said(page, '#disc-plan [data-recorded-ticket]')).includes('History, not an order to place'), await said(page, '#disc-plan [data-recorded-ticket]'));
  await openAll(page, '#orders');
  check('the ticket sheet says the window ended in its own summary',
    (await text(page, '#orders-summary')).includes('window ended') && (await text(page, '#orders-summary')).startsWith(forDay), await text(page, '#orders-summary'));
  eq('and offers no order row', await count(page, '#order-sheet tbody tr[data-ticker]'), 0);
  check('naming the window rather than staleness', (await said(page, '#order-sheet tbody .sc-empty')).includes('window'), await said(page, '#order-sheet tbody .sc-empty'));

  // ---- the same surfaces INSIDE the window: offered, and honest about what
  // the page cannot see
  await phaseAt(page, next, 'inside');
  eq('inside the window the sheet offers its order again', await count(page, '#order-sheet tbody tr[data-ticker]'), 1);
  await openAll(page, '#disc-plan');
  eq('and the copy control is back', await count(page, '#disc-plan [data-copy]'), 1);
  check('the next action says the window is in progress, not that a trigger has been met',
    (await text(page, '#next-h3')).includes('is in progress') && /not verified here/.test(await text(page, '#next-p')), await text(page, '#next-p'));
  check('the last observed data timestamp stays visible inside the window',
    /published \d+:\d\d [AP]M ET/.test(await said(page, '#market-facts [data-fact="data"]')), await said(page, '#market-facts [data-fact="data"]'));
  check('the action bar names the window it fills inside, and never "tomorrow"',
    (await said(page, '.ss-action')).includes(next.run.timing.applicable_session) && !/tomorrow/i.test(await said(page, '.ss-action')), await said(page, '.ss-action'));

  // ---- a tab left open ACROSS the deadline, the clock its own
  {
    const { context: c2, page: p2, errors: e2 } = await open(browser, base, '/tests/fixtures/page/next.json', null, 1280,
      { lens: 'all', hash: `#/explore/bursts/${order}` });
    // the page's own clock, moved by moving Date itself: the tab was opened
    // inside the window and is still open an hour after it closed
    await p2.evaluate((iso) => {
      const Real = Date, fixed = new Real(iso).getTime();
      window.__fake = fixed;
      function Fake(...a) { return a.length ? new Real(...a) : new Real(window.__fake); }
      Fake.now = () => window.__fake; Fake.parse = Real.parse; Fake.UTC = Real.UTC;
      Fake.prototype = Real.prototype;
      window.Date = Fake;
    }, WHEN.inside[0]);
    await p2.evaluate(() => window.SCStock.reclock());
    eq('a tab opened inside the window says so', await attr(p2, 'html', 'data-ss-window'), 'open');
    const chartBefore = await p2.evaluate(() => window.SCStock.liveCharts());
    await openAll(p2, '#disc-plan');
    await p2.locator('#disc-plan [data-copy]').first().focus();
    await p2.evaluate((iso) => { window.__fake = new Date(iso).getTime(); }, WHEN.after[0]);
    const moved = await p2.evaluate(() => window.SCStock.reclock());
    eq('crossing the deadline while it sits there changes the answer', [moved, await attr(p2, 'html', 'data-ss-window')], [true, 'ended']);
    check('the left-open tab now says the window ended', (await text(p2, '#next-h3')).includes('has ended'), await text(p2, '#next-h3'));
    eq('and the copy control is gone from under the reader', await count(p2, '#disc-plan [data-copy]'), 0);
    eq('the chart was NOT torn down to say so', await p2.evaluate(() => window.SCStock.liveCharts()), chartBefore);
    eq('the plan disclosure the reader had open stays open', await p2.evaluate(() => document.getElementById('disc-plan').open), true);
    check('and the focus did not fall on the body',
      await p2.evaluate(() => document.activeElement !== document.body && document.activeElement.tagName !== 'HTML'),
      await p2.evaluate(() => document.activeElement.tagName + '/' + document.activeElement.className));
    // a second re-reading with nothing changed repaints nothing
    eq('a re-reading that changes no answer repaints nothing', await p2.evaluate(() => window.SCStock.reclock()), false);
    eq('left-open-tab page errors', e2, []);
    await c2.close();
  }

  // ---- a copy that is pressed after the window closed under it
  {
    const { context: c3, page: p3, errors: e3 } = await open(browser, base, '/tests/fixtures/page/next.json', null, 1280,
      { lens: 'all', hash: `#/explore/bursts/${order}` });
    await p3.evaluate((iso) => {
      const Real = Date, fixed = new Real(iso).getTime();
      window.__fake = fixed;
      function Fake(...a) { return a.length ? new Real(...a) : new Real(window.__fake); }
      Fake.now = () => window.__fake; Fake.parse = Real.parse; Fake.UTC = Real.UTC; Fake.prototype = Real.prototype;
      window.Date = Fake;
    }, WHEN.last[0]);
    await p3.evaluate(() => window.SCStock.reclock());
    await openAll(p3, '#disc-plan');
    eq('a reader inside the window has a copy control', await count(p3, '#disc-plan [data-copy]'), 1);
    // the window closes while the disclosure is open, and the page is NOT told
    await p3.evaluate((iso) => { window.__fake = new Date(iso).getTime(); }, WHEN.after[0]);
    // Chromium's clipboard is shared across the contexts of one browser, so
    // "it is empty" is no evidence on its own: a suite that copied earlier
    // would have left its own text there. It is written first, and must be
    // exactly what is read back.
    await p3.evaluate(() => navigator.clipboard.writeText('nothing was copied').catch(() => {}));
    await p3.locator('#disc-plan [data-copy]').first().click();
    await p3.waitForTimeout(250);
    const clip = await p3.evaluate(() => navigator.clipboard.readText().catch(() => ''));
    eq('pressing it after the window closed copies nothing', clip, 'nothing was copied');
    // the refusal is said in the action area, because catching the page up
    // rebuilds the disclosure the button was in
    const refused = await said(p3, '[data-copy-refused]');
    check('and says, where the reader is looking, that nothing was copied',
      refused.includes('Nothing was copied') && refused.includes('ended'), refused);
    check('the rest of the page catches up with it', (await text(p3, '#next-h3')).includes('has ended'), await text(p3, '#next-h3'));
    eq('late-copy page errors', e3, []);
    await c3.close();
  }

  // ---- timing NARROWS and never widens
  {
    // a red night's headline stays the regime's, with the window said beside it
    const r = await open(browser, base, '/tests/fixtures/page/red.json', atSession(red.run.timing, '09:00'), 1280, { lens: 'all' });
    check('a red night still leads with no new longs, whatever the clock',
      (await text(r.page, '#next-h3')).startsWith('No new longs'), await text(r.page, '#next-h3'));
    check('and the window is named beside it, not instead of it',
      (await text(r.page, '#next-p')).includes('entry window for'), await text(r.page, '#next-p'));
    eq('red-night page errors', r.errors, []);
    await r.context.close();
    // A holiday reads the unchanged Friday publication, applicable Tuesday.
    const clTm = closed.run.timing;
    const cl = await open(browser, base, '/tests/fixtures/page/closed.json', '2026-09-07T22:31:00Z', 1280, { lens: 'all' });
    check('a known holiday preserves the Friday plan and names the actual Tuesday session',
      (await text(cl.page, '#status-line')).includes('8 Sep') && clTm.applicable_session === '2026-09-08', await text(cl.page, '#status-line'));
    eq('closed-night page errors', cl.errors, []);
    await cl.context.close();
    // a stale page is refused whatever the window says: publication first
    const s = await open(browser, base, '/tests/fixtures/page/full.json', STALE2_NOW, 1280, { lens: 'all', hash: `#/explore/bursts/${full.trades[0]}` });
    const openWindow = await s.page.evaluate((d) => {
      // a window that IS open, on a record the page is four sessions behind on
      const forged = JSON.parse(JSON.stringify(d));
      forged.run.timing.applicable_session = '2026-09-16';
      forged.run.timing.opens_at = '2026-09-16T09:30:00-04:00';
      forged.run.timing.cutoff_at = '2026-09-16T10:00:00-04:00';
      forged.run.timing.prepare_by = '2026-09-16T09:28:00-04:00';
      forged.run.timing.closes_at = '2026-09-16T16:00:00-04:00';
      window.SCStock.render(forged, new Date('2026-09-16T13:40:00Z'));
      const a = window.SCStock.avail;
      return { phase: a.phase, offered: a.offered, lead: a.lead, pub: a.pub.state };
    }, full);
    eq('an OPEN window cannot make a stale page actionable', [openWindow.phase, openWindow.pub, openWindow.offered], ['open', 'stale2', false]);
    eq('and the reason given is the staleness, not the clock', openWindow.lead, 'not offered');
    eq('stale-page page errors', s.errors, []);
    await s.context.close();
  }

  // ---- a record with no timing block at all: research only
  {
    const { context: c4, page: p4, errors: e4 } = await open(browser, base, '/tests/fixtures/page/next.json', WHEN.evening[0], 1280,
      { lens: 'all', hash: `#/explore/bursts/${order}` });
    const legacy = await p4.evaluate((d) => {
      const old = JSON.parse(JSON.stringify(d));
      delete old.run.timing;
      window.SCStock.render(old, new Date('2026-09-11T22:31:00Z'));
      const a = window.SCStock.avail;
      return { phase: a.phase, offered: a.offered, lead: a.lead, reason: a.reason };
    }, next);
    eq('a record published before the field existed is unknown, and offers nothing', [legacy.phase, legacy.offered], ['unknown', false]);
    check('and says research only in those words', legacy.reason.includes('Entry timing unavailable — research only'), legacy.reason);
    check('the plan line says the timing is not recorded rather than inventing one',
      (await said(p4, '#market-facts [data-fact="plan"]')).includes('entry timing unavailable'), await said(p4, '#market-facts [data-fact="plan"]'));
    eq('no order is offered from it', await count(p4, '#order-sheet tbody tr[data-ticker]'), 0);
    await openAll(p4, '#disc-plan');
    eq('and no copy control', await count(p4, '#disc-plan [data-copy]'), 0);
    // a half-written block is worse than none and reads the same way
    for (const [what, mutate] of [
      ['a cutoff before its own opening', (t) => { t.cutoff_at = '2026-09-14T09:00:00-04:00'; }],
      ['an instant with no offset', (t) => { t.opens_at = '2026-09-14T09:30:00'; }],
      ['an opening on another session', (t) => { t.opens_at = '2026-09-15T09:30:00-04:00'; }],
      ['no applicable session', (t) => { delete t.applicable_session; }],
    ]) {
      const got = await p4.evaluate(([d, which]) => {
        const bad = JSON.parse(JSON.stringify(d));
        const t = bad.run.timing;
        if (which === 0) t.cutoff_at = '2026-09-14T09:00:00-04:00';
        if (which === 1) t.opens_at = '2026-09-14T09:30:00';
        if (which === 2) t.opens_at = '2026-09-15T09:30:00-04:00';
        if (which === 3) delete t.applicable_session;
        window.SCStock.render(bad, new Date('2026-09-14T13:40:00Z'));
        return { phase: window.SCStock.avail.phase, faults: window.SCStock.timingFaults(bad).length };
      }, [next, [['a cutoff before its own opening', 0], ['an instant with no offset', 1], ['an opening on another session', 2], ['no applicable session', 3]].findIndex((x) => x[0] === what)]);
      check(`${what} is refused rather than compared against`, got.phase === 'unknown' && got.faults > 0, JSON.stringify(got));
    }
    eq('legacy-record page errors', e4, []);
    await c4.close();
  }
  eq('session page errors', errors, []);
  if (shotsDir) {
    await mkdir(shotsDir, { recursive: true });
    for (const [w, h] of [[1280, 900], [390, 844], [320, 720]]) {
      await page.setViewportSize({ width: w, height: h });
      await page.waitForTimeout(250);
      await go(page, '#/explore');
      await phaseAt(page, next, 'after');
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(shotsDir, `session-ended-${w}.png`) });
      eq(`the compact area does not scroll sideways at ${w} px`,
        await page.evaluate(() => document.getElementById('market-bar').scrollWidth <= document.documentElement.clientWidth + 1), true);
      eq(`nor does the page at ${w} px`,
        await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), w >= 320);
      await phaseAt(page, next, 'inside');
      await page.screenshot({ path: path.join(shotsDir, `session-open-${w}.png`) });
    }
  }
  await context.close();
}

// ---------------------------------------------------------------------------
// Check for updates: re-reading the same static file, transactionally, without
// taking the reader's place with it. Every answer is served by a route so the
// suite decides what the file says -- unchanged, newer, older, a revision of
// the same session, unreadable, or nothing at all.
// ---------------------------------------------------------------------------
async function checkRefresh(browser, base, full) {
  console.log('-- refresh: loading a newer record safely, and saying what it cost');
  const next = JSON.parse(await readFile(path.join(FIXTURES, 'next.json'), 'utf8'));
  const revised = JSON.parse(await readFile(path.join(FIXTURES, 'revised.json'), 'utf8'));
  const said2 = (page) => text(page, '#refresh-said');
  const press = async (page) => { await page.locator('#check-updates').click(); await page.waitForTimeout(450); };
  // whatever the route is told to answer with next; null aborts the request
  const serveWith = async (page, url, box) => {
    await page.route(url, async (route) => {
      const answer = box.body;
      if (answer === null) return route.abort('failed');
      if (box.delayMs) await new Promise((r) => setTimeout(r, box.delayMs));
      return route.fulfill({ status: box.status || 200, contentType: 'application/json',
        body: typeof answer === 'string' ? answer : JSON.stringify(answer) });
    });
  };

  // ---- booted on the OLDER record, so a newer one is a real forward step
  const box = { body: next };
  const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, 1280,
    { lens: 'all', hash: `#/explore/bursts/${full.trades[0]}` });
  await serveWith(page, '**/full.json?*', box);
  check('the control is beside the publication line it re-reads',
    !!(await count(page, '#market-bar #market-refresh #check-updates')), 'no control in the market area');
  check('and says what it does and does not do, without a line of its own at rest',
    (await attr(page, '#check-updates', 'title')).includes('Nothing is scanned or graded') &&
    (await page.locator('#refresh-said').isHidden()), await attr(page, '#check-updates', 'title'));

  // the reader's own state, set before anything is re-read
  await setLens(page, 'a');
  await page.locator('#search').fill('AA');
  await page.locator('#pick-list .ss-pick').first().click();
  await page.waitForTimeout(200);
  const wasStock = await attr(page, '#detail', 'data-selected'), wasLens = await lensNow(page);
  await page.click('#detail .sc-tab[data-mode="candles"]');
  await page.waitForTimeout(200);
  await page.locator('[data-follow-action="add"]').first().click();
  await page.waitForTimeout(250);
  const ids = async (pg) => ((await readStore(pg)) || { items: [] }).items.map((x) => x.id);
  const bars = async (pg) => ((await readStore(pg)) || { items: [] }).items.map((x) => ((x.evidence || {}).series || []).length);
  const obsCounts = async (pg) => ((await readStore(pg)) || { items: [] }).items.map((x) => (x.observations || []).length);
  const savedIds = await ids(page), savedEvidence = await bars(page);
  eq('a setup is saved before the reload', savedIds.length, 1);

  // ---- unchanged: the same BYTES, and nothing at all moves. The file's own
  // text, not a re-serialization of it: "unchanged" means the served file is
  // identical, which is the only reading that catches a same-session
  // re-publish whose session, publish stamp and rules digest all match.
  box.body = await readFile(path.join(FIXTURES, 'full.json'), 'utf8');
  const obsBefore = await obsCounts(page);
  await press(page);
  eq('the same record is reported unchanged', (await said2(page)).startsWith('No newer record'), true);
  eq('and the reader is left exactly where they were', [await attr(page, '#detail', 'data-selected'), await lensNow(page), await page.locator('#search').inputValue()], [wasStock, wasLens, 'AA']);
  eq('an unchanged check adds no Following observation', await obsCounts(page), obsBefore);

  // ---- unreadable, and then unreachable: nothing changes, and it says so
  for (const [what, body, starts] of [
    ['not a record this page can read', {}, 'The published file is not a record'],
    ['a record whose window has no width', JSON.parse(JSON.stringify(Object.assign({}, next, { run: Object.assign({}, next.run, { timing: Object.assign({}, next.run.timing, { cutoff_at: next.run.timing.opens_at }) }) }))), 'The published file is not a record'],
    ['not JSON at all', 'half a fi', 'The published record could not be re-read'],
    ['nothing at all', null, 'The published record could not be re-read'],
  ]) {
    box.body = body;
    await press(page);
    check(`${what}: it is not loaded`, (await said2(page)).startsWith(starts), await said2(page));
    eq(`${what}: and the record on screen is untouched`, await page.evaluate(() => window.SCStock.data.run.session), full.run.session);
    eq(`${what}: with the reader still where they were`, await attr(page, '#detail', 'data-selected'), wasStock);
  }

  // ---- out of order: a slow first answer cannot land over a fast second
  {
    box.body = next; box.delayMs = 900;
    await page.locator('#check-updates').click();
    await page.waitForTimeout(120);
    eq('a check in flight says so on the control', await attr(page, '#check-updates', 'data-check'), 'busy');
    check('and the control is still pressable, so a hanging check is not a dead end',
      !(await page.locator('#check-updates').isDisabled()), 'the control went dead while checking');
    // the second press answers at once, with the file's own bytes, so its
    // outcome ("unchanged") is unmistakably different from the slow one's
    box.body = await readFile(path.join(FIXTURES, 'full.json'), 'utf8'); box.delayMs = 0;
    await page.locator('#check-updates').click();
    await page.waitForTimeout(1600);
    check('the answer that stands is the newest press, not the first to arrive',
      (await said2(page)).startsWith('No newer record'), await said2(page));
    eq('and the slow answer was dropped rather than applied', await page.evaluate(() => window.SCStock.data.run.session), full.run.session);
  }

  // ---- a comparison open across the load: explained, not remapped
  {
    await page.locator('#search').fill('');
    await setLens(page, 'all');
    await page.waitForTimeout(250);
    const two = (await cardTickers(page)).slice(0, 2);
    eq('the whole stage is in view, so two can be pinned', two.length, 2);
    for (const t of two) { await page.click(`#pick-list .ss-pick-item:has(.ss-pick[data-ticker="${t}"]) .ss-pin`); await page.waitForTimeout(180); }
    await tap(page, '#compare-open', 'the comparison opens before the load');
    await page.waitForTimeout(500);
    eq('two are pinned and compared', await count(page, '#compare .ss-compare__side'), 2);
    box.body = next;
    // the comparison is a real modal, so the control behind it cannot be
    // clicked -- which is right. The case still has to be handled: a load can
    // reach the page while the sheet stands (a reader with two tabs, a press
    // whose answer arrives late), so it is driven directly here.
    eq('the control is behind the comparison, as a modal means it to be',
      await page.evaluate(() => {
        const b = document.getElementById('check-updates').getBoundingClientRect();
        return document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2) !== document.getElementById('check-updates');
      }), true);
    await page.evaluate(() => window.SCStock.checkUpdates());
    await page.waitForTimeout(500);
    check('a newer record is loaded', (await said2(page)).startsWith('A newer record loaded'), await said2(page));
    eq('the comparison is closed rather than remapped onto other stocks', await page.evaluate(() => document.getElementById('compare').open), false);
    check('and the reader is told why, in the same breath',
      (await said2(page)).includes('pinned pair belongs to the record it was pinned from'), await said2(page));
    eq('no chart is left mounted from it', await page.evaluate(() => window.SCStock.liveCharts()), 1);
    eq('the record on screen is the newer one', await page.evaluate(() => window.SCStock.data.run.session), next.run.session);
  }

  // ---- the reader's private saves are untouched by any of it
  eq('every saved identity survives the load', await ids(page), savedIds);
  eq('with its frozen evidence unchanged', await bars(page), savedEvidence);
  eq('and the chart mode the reader chose is still theirs',
    await page.evaluate(() => (JSON.parse(localStorage.getItem('spicystock:chart:v1')) || {}).mode), 'candles');
  // one deliberate abort: the request itself, and the browser's anonymous
  // console line for it. Named here rather than swept into the exempt list,
  // because it is this check's own doing and nothing else's.
  eq('the only failures are the one request this check aborted on purpose',
    errors.filter((e) => !/full\.json\?at=/.test(e) && e !== 'console: Failed to load resource: net::ERR_FAILED'), []);
  eq('and it is exactly one request', errors.filter((e) => /^request failed/.test(e)).length, 1);
  await context.close();

  // ---- older, a revision, and a half-typed reference size
  {
    const b2 = { body: revised };
    const { context: c2, page: p2, errors: e2 } = await open(browser, base, '/tests/fixtures/page/next.json', '2026-09-11T22:31:00Z', 1280,
      { lens: 'all', hash: `#/explore/bursts/${next.trades[0]}` });
    await serveWith(p2, '**/next.json?*', b2);
    b2.body = full;
    await press(p2);
    check('a file for an EARLIER session is refused rather than applied backwards',
      (await said2(p2)).startsWith('The published file is for an earlier session'), await said2(p2));
    eq('and the newer record stays on screen', await p2.evaluate(() => window.SCStock.data.run.session), next.run.session);

    // a follow, then a half-typed size, then a load
    await p2.locator('[data-follow-action="add"]').first().click();
    await p2.waitForTimeout(250);
    await p2.locator('[data-follow-action="edit"]').first().click();
    await p2.waitForTimeout(200);
    await p2.locator('.ss-follow__form input').first().fill('17');
    const savedShares = (await readStore(p2)).items[0].reference_shares;
    b2.body = revised;
    await press(p2);
    check('the same session re-published is called a revision, not a new day',
      (await said2(p2)).includes('the same session on later bars, not a new one'), await said2(p2));
    eq('the record loaded is the revision', await p2.evaluate(() => [window.SCStock.data.run.session, window.SCStock.data.run.published_at]),
      [revised.run.session, revised.run.published_at]);
    eq('a half-typed reference size is handed back, unsaved', [await p2.locator('.ss-follow__form input').first().inputValue(),
      (await readStore(p2)).items[0].reference_shares], ['17', savedShares]);
    check('and a revision is recorded as a revision of that trading day',
      ((await readStore(p2)).items[0].observations || []).every((o) => !o.replaced || o.replaced.c !== o.c), 'a revision lost what it replaced');
    // a saved setup's own sheet, open across a load: it is this browser's, so
    // it survives a record change by construction -- proved, not assumed
    const id = (await readStore(p2)).items[0].id;
    await go(p2, `#/followed/${encodeURIComponent(id)}`);
    await p2.waitForTimeout(400);
    eq('a saved setup sheet is open before the load', await p2.evaluate(() => document.getElementById('saved').open), true);
    b2.body = next;
    // a saved sheet is a modal too, and the same reasoning applies
    eq('the control is behind the saved sheet, as a modal means it to be',
      await p2.evaluate(() => {
        const b = document.getElementById('check-updates').getBoundingClientRect();
        return document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2) !== document.getElementById('check-updates');
      }), true);
    await p2.evaluate(() => window.SCStock.checkUpdates());
    await p2.waitForTimeout(500);
    eq('and is still open, on the same saved identity, after it',
      [await p2.evaluate(() => document.getElementById('saved').open), await attr(p2, '#saved [data-saved-id]', 'data-saved-id')], [true, id]);
    eq('older-and-revision page errors', e2, []);
    await c2.close();
  }
}

async function checkReaderCommentary(browser, base) {
  console.log('-- retained reader commentary (local presentation excerpt, not live publication acceptance)');
  const dir = path.join(ROOT, 'tests/fixtures/grading/reader-commentary');
  const contextRecord = JSON.parse(await readFile(path.join(dir, 'record.json'), 'utf8'));
  const rows = await Promise.all(['JRSH', 'JKHY'].map(async ticker => JSON.parse(await readFile(path.join(dir, `burst-${ticker}.json`), 'utf8')).row));
  const record = { schema_version: 2, ...contextRecord, bursts: rows, watchlist: { top: [], also_quiet: [] } };
  for (const width of [1280, 390, 320]) for (const theme of ['dark', 'light']) {
    const requests = [];
    const { context, page, errors } = await open(browser, base, '/reader-excerpt.json', '2026-09-16T22:30:00Z', width, {
      theme, hash: '#/explore/bursts/JRSH', beforeLoad: async page => {
        page.on('request', r => { if (r.url().includes('/evidence/')) requests.push(r.url()); });
        await page.route('**/reader-excerpt.json', route => route.fulfill({ json: record }));
      }
    });
    const name = `retained JRSH ${width}/${theme}`;
    const why = await text(page, '#detail [data-item="why"]');
    check(name + ' primary explanation uses recorded grades', why.includes('checklist A; published C') && !why.includes(rows[0].claude.reason));
    await page.locator('#disc-provenance > summary').focus();
    await page.keyboard.press('Enter');
    check(name + ' keyboard opens provenance', await page.locator('#disc-provenance').evaluate(el => el.open));
    const focus = await page.locator('#disc-provenance > summary').evaluate(el => ({ active: document.activeElement === el, outline: getComputedStyle(el).outlineStyle }));
    check(name + ' keyboard focus is visible', focus.active && !['none', 'hidden'].includes(focus.outline), focus);
    const prov = await text(page, '#disc-provenance');
    check(name + ' original commentary is qualified before raw text', prov.includes('Recorded checklist criteria govern thresholds') && prov.indexOf('commentary is unverified') >= 0 && prov.indexOf('commentary is unverified') < prov.indexOf(rows[0].claude.reason));
    for (const field of ['reason', 'key_risk', 'entry_note']) check(name + ' preserves ' + field, prov.includes(rows[0].claude[field]));
    check(name + ' fits viewport', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    eq(name + ' zero initial evidence requests', requests, []);
    if (shotsDir) {
      await mkdir(shotsDir, { recursive: true });
      await page.locator('#detail .ss-decision').screenshot({ path: path.join(shotsDir, `reader-JRSH-decision-${width}-${theme}.png`) });
      await page.locator('#disc-provenance').screenshot({ path: path.join(shotsDir, `reader-JRSH-provenance-${width}-${theme}.png`) });
    }
    await go(page, '#/explore/bursts/JKHY');
    check(name + ' unreviewed Dollar-only control has red no-entry reason', (await text(page, '#detail [data-no-entry-reason]')).includes('breadth is red'));
    await page.locator('#disc-provenance > summary').click();
    const unreviewed = await text(page, '#disc-provenance');
    check(name + ' unreviewed control does not invent reader commentary', unreviewed.includes('checklist alone') && !unreviewed.includes('commentary is unverified'));
    eq(name + ' runtime errors', errors.slice(), []);
    await context.close();
  }
}

async function checkGradingHistory(browser, base) {
  console.log('-- grading history');
  const dir = path.join(ROOT, 'tests', 'fixtures', 'grading');
  const audit = JSON.parse(await readFile(path.join(dir, 'history-audit.json'), 'utf8'));
  const id = 'a89ab122d7e0160df6a63c30957668447ace1103';
  const entries = audit.rows.filter(r => ['CACI', 'ROKU'].includes(r.ticker)).map(r => ({
    ticker: r.ticker, kind: 'burst', grade: r.final_grade, scan: r.scan,
    source: id, path: r.path, sha256: r.sha256, chart: false
  }));
  // Pin the original public contract; this test outlives its rolling retention.
  const index = { version: 1, as_of: audit.history_as_of, days: audit.days,
    dates: audit.dates, records: { [id]: audit.sources[id] }, entries };
  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [320, 'dark'], [320, 'light']]) {
    const { context, page, errors } = await open(browser, base, '/tests/fixtures/page/full.json',
      '2026-09-15T22:31:00Z', width, { theme, hash: '#/setups' });
    await page.route('**/history/index.json', route => route.fulfill({ json: index }));
    await page.route(`**/history/${id}/*.json`, async route => {
      const name = new URL(route.request().url()).pathname.split('/').at(-1);
      await route.fulfill({ contentType: 'application/json', body: await readFile(path.join(dir, name), 'utf8') });
    });
    await page.locator('#earlier-setups summary').click();
    for (const ticker of ['CACI', 'ROKU']) {
      const original = JSON.parse(await readFile(path.join(dir, `burst-${ticker}.json`), 'utf8')).row;
      await page.locator('#history-ticker').fill(ticker);
      await page.locator('#history-search button').click();
      await page.locator(`[data-history-inspect="${id}"]`).click();
      await page.locator('[data-history-save]').waitFor();
      const preview = await text(page, '#history-results');
      check(`${ticker} ${width}/${theme} original reason is visibly historical`,
        preview.includes('Historical research only.') && preview.includes('Original chart reader: ' + original.claude.reason));
      check(`${ticker} ${width}/${theme} original commentary has no rule authority`,
        preview.includes('commentary is unverified') && preview.includes('Recorded checklist criteria govern thresholds'));
      check(`${ticker} ${width}/${theme} exact session, scan, source and unchanged grade`,
        preview.includes('2026-09-14') && preview.includes('scan dollar') && preview.includes(id) &&
        preview.includes('Published grade: ' + original.grade));
      eq(`${ticker} ${width}/${theme} recovery creates no ticket`, await count(page, '#history-results [data-order-copy]'), 0);
      check(`${ticker} ${width}/${theme} page fits viewport`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (shotsDir && ticker === 'ROKU') {
        await mkdir(shotsDir, { recursive: true });
        await page.locator('#history-results').screenshot({ path: path.join(shotsDir, `grading-history-${width}-${theme}.png`) });
      }
    }
    eq(`grading history ${width}/${theme} runtime errors`, errors.slice(), []);
    await context.close();
  }
}

async function checkInputCoverage(browser, base) {
  for (const width of [1280, 390, 320]) {
    for (const variant of ['partial', 'empty']) {
      const data = JSON.parse(await readFile(path.join(FIXTURES, variant + '.json'), 'utf8'));
      const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/' + variant + '.json', FRESH_NOW, width);
      const cov = data.run.coverage, a = cov.acceptance;
      const coverText = await said(page, '#cover-dek');
      check(variant + ' ' + width + ': honest empty headline', (await said(page, '#cover-h1')).includes(variant === 'partial' ? 'evaluated subset' : 'Nothing qualifies'));
      check(variant + ' ' + width + ': coverage beside verdict', coverText.includes(a.ready_stocks + ' of ' + a.intended_stocks + ' intended stocks'), coverText);
      if (variant === 'partial') {
        await go(page, '#/method');
        await page.locator('#cover-record > summary').click();
        const coverage = await said(page, '#cover-coverage');
        check('full coverage counts and scope remain inspectable in Method', coverage.includes(cov.unfetched_budget + ' fetch names were never attempted') && coverage.includes('fetch counts include the benchmark'));
        check('incomplete-input meaning stays visible', coverText.includes('Incomplete coverage.') && (await said(page, '#status-line')).includes('Missing inputs are unknown'));
        check('empty workspace retains coverage warning', (await said(page, '[data-empty=bursts]')).includes('Incomplete input coverage'));
        check('next-action message retains coverage warning', (await said(page, '#next-p')).includes('Incomplete input coverage'));
      }
      await go(page, '#/method');
      const method = await said(page, '#run-meta');
      for (const words of ['split-adjusted (not dividend-adjusted)', 'historical point-in-time membership',
          'intended stocks', 'budget-unfetched', 'missing required previous session', 'Expected 2026-09-10']) {
        check(variant + ' ' + width + ': Method says ' + words, method.includes(words), method);
      }
      check('Method reports ready denominator', (await said(page, '#run-strip')).includes(a.ready_stocks + ' of ' + a.intended_stocks));
      check('Method has no horizontal overflow at ' + width, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      eq('input page has no browser errors', errors.length, 0);
      if (shotsDir && variant === 'partial') {
        await mkdir(shotsDir, { recursive: true });
        await page.screenshot({ path: path.join(shotsDir, 'inputs-method-' + width + '.png'), fullPage: true });
        await go(page, '#/explore');
        await page.screenshot({ path: path.join(shotsDir, 'inputs-empty-' + width + '.png'), fullPage: true });
      }
      await context.close();
    }
  }
  const legacy = JSON.parse(await readFile(path.join(FIXTURES, 'empty.json'), 'utf8'));
  delete legacy.run.coverage.version; delete legacy.run.coverage.acceptance; delete legacy.run.input_basis;
  legacy.cover.dek = 'No reaction candidates were recorded.';
  const filename = path.join(ROOT, 'tests/fixtures/page/_inputs-legacy.json');
  await writeFile(filename, JSON.stringify(legacy));
  try {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/_inputs-legacy.json', FRESH_NOW, 390);
    check('legacy empty result stays unknown', (await said(page, '#cover-dek')).includes('Input completeness was not recorded'));
    await go(page, '#/method');
    check('legacy basis is not backfilled', (await said(page, '#run-meta')).includes('adjustment basis not recorded'));
    check('legacy stats do not invent completeness', (await said(page, '#run-strip')).includes('not recorded'));
    eq('legacy inputs browser errors', errors.length, 0);
    await context.close();
  } finally { await unlink(filename); }
}

async function checkExchangeCalendar(browser, base) {
  console.log('-- exchange calendar');
  const holiday = JSON.parse(await readFile(path.join(FIXTURES, 'closed.json'), 'utf8'));
  const early = JSON.parse(await readFile(path.join(FIXTURES, 'early.json'), 'utf8'));
  for (const width of [1280, 390]) {
    const h = await open(browser, base, '/tests/fixtures/page/closed.json', '2026-09-07T22:31:00Z', width, { lens: 'all' });
    eq('holiday keeps the Friday measured date', holiday.run.session, '2026-09-04');
    eq('holiday plan applies Tuesday', holiday.run.timing.applicable_session, '2026-09-08');
    eq('holiday is closed, with no false missing-session count', await h.page.evaluate((data) => [SCStock.status(data, new Date('2026-09-07T22:31:00Z')).state], holiday), ['closed']);
    check('dated Tuesday action survives the holiday', (await text(h.page, '#next-p')).includes('8 Sep'), await text(h.page, '#next-p'));
    await go(h.page, '#/record');
    eq('reliability row does not invent a missing Labor Day session', await count(h.page, '#nights [data-session="2026-09-07"]'), 0);
    if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await go(h.page, '#/explore'); await h.page.screenshot({ path: path.join(shotsDir, `calendar-holiday-${width}.png`) }); }
    eq('holiday calendar page errors', h.errors, []); await h.context.close();
    const e = await open(browser, base, '/tests/fixtures/page/early.json', '2024-11-29T17:59:00Z', width, { lens: 'all', hash: '#/method' });
    const method = await text(e.page, '#run-meta');
    check('actual early close is rendered with provenance', method.includes('2024-11-29T13:00:00-05:00') && method.includes('shortened session') && method.includes('exchange_calendars 4.13.2'), method);
    const phases = await e.page.evaluate((data) => ['2024-11-29T18:14:59Z', '2024-11-29T18:15:00Z'].map((at) => {
      const s = SCStock.status(data, new Date(at)); return [s.expected, s.state];
    }), early);
    eq('early close completion buffer gates freshness', phases, [['2024-11-27', 'fresh'], ['2024-11-29', 'pending']]);
    if (shotsDir) await e.page.screenshot({ path: path.join(shotsDir, `calendar-early-${width}.png`), fullPage: true });
    const cases = await e.page.evaluate((data) => {
      const legacy = JSON.parse(JSON.stringify(data)); delete legacy.run.calendar;
      const unknown = SCStock.availability(legacy, new Date('2024-11-29T14:40:00Z'));
      const far = SCStock.availability(data, new Date('2025-03-01T14:40:00Z'));
      return [unknown.pub.state, unknown.offered, far.pub.state, far.offered, legacy.run.timing.closes_at];
    }, early);
    eq('legacy and out-of-window calendar evidence never authorizes action', cases, ['unknown', false, 'unknown', false, '2024-11-29T13:00:00-05:00']);
    eq('early-close page errors', e.errors, []); await e.context.close();
  }
}

async function checkPlanEvidence(browser, base) {
  console.log('-- plan evidence');
  for (const width of [1280, 390, 320]) for (const theme of ['dark', 'light']) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH_NOW, width,
      { theme, lens: 'all', hash: '#/explore/bursts/AAPL' });
    await page.locator('#disc-provenance > summary').click();
    const technical = page.locator('#disc-provenance details');
    eq('technical hashes start collapsed', await technical.getAttribute('open'), null);
    check('receipt explains that a ticket existed', (await text(page, '[data-plan-evidence]')).includes('A conditional ticket was published.'));
    if (shotsDir) {
      await mkdir(shotsDir, { recursive: true });
      await page.locator('#disc-provenance').screenshot({ path: path.join(shotsDir, `provenance-${width}-${theme}.png`) });
    }
    await technical.locator('summary').click();
    check('technical reference wraps within mobile width', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    eq('provenance browser errors', errors, []);
    await context.close();
  }
  const red = await open(browser, base, '/tests/fixtures/page/red.json', FRESH_NOW, 390,
    { lens: 'all', hash: '#/explore/bursts/AAPL' });
  await red.page.locator('#disc-provenance > summary').click();
  check('red receipt explains the regime refusal', (await text(red.page, '[data-plan-evidence]')).includes('No ticket: regime gate.'));
  if (shotsDir) await red.page.locator('#disc-provenance').screenshot({ path: path.join(shotsDir, 'provenance-red-390.png') });
  eq('red provenance browser errors', red.errors, []);
  await red.context.close();
}

async function main() {
  const chromium = await loadChromium();
  if (!chromium) { console.log('playwright is not installed: npm install --no-save playwright'); process.exit(1); }
  for (const v of VARIANTS.concat(SEQUELS)) if (!existsSync(path.join(FIXTURES, `${v}.json`))) { console.log(`missing fixture ${v}.json -- run python tools/make_fixture.py`); process.exit(1); }
  const { server, base } = await serve();
  const browser = await chromium.launch();
  try {
    let full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
    for (const v of VARIANTS) {
      if (!runs(v)) continue;
      const data = JSON.parse(await readFile(path.join(FIXTURES, `${v}.json`), 'utf8'));
      await checkVariant(browser, base, v, data);
    }
    if (runs('actionability') || runs('actionability-core')) await checkActionability({ browser, base, data: full, open, check, eq, shotsDir, coreOnly: !!only && only.includes('actionability-core') });
    if (runs('focus')) await checkEvidenceFocus({ browser, base, data: full, open, check, eq, shotsDir });
    if (runs('reading')) await checkReading({ browser, base, data: full, open, check, eq, shotsDir });
    if (runs('panes')) await checkExplorePanes({ browser, base, data: full, open, check, eq, shotsDir });
    if (runs('followed-plan')) await checkFollowedPlan({browser, base, data: full, open, check, eq, shotsDir});
    if (runs('scorecard')) await checkScorecard({browser, base, data: full, open, check, eq, shotsDir});
    if (runs('calendar')) await checkExchangeCalendar(browser, base);
    if (runs('provenance')) await checkPlanEvidence(browser, base);
    if (runs('mobile')) await checkMobile(browser, base, full);
    if (runs('modes')) await checkModes(browser, base, full);
    if (runs('lens')) await checkLens(browser, base, full);
    if (runs('compare')) await checkCompare(browser, base, full);
    if (runs('evidence')) await checkEvidence(browser, base, full);
    if (runs('map')) await checkMap(browser, base, full);
    if (runs('reach')) await checkReach(browser, base, full);
    if (runs('volume')) await checkVolumeReadings(browser, base, full);
    if (runs('mapscale')) await checkMapScale(browser, base, full);
    if (runs('following')) await checkFollowing(browser, base, full);
    if (runs('through')) await checkFollowThrough(browser, base, full);
    if (runs('session')) await checkSession(browser, base, full);
    if (runs('refresh')) await checkRefresh(browser, base, full);
    if (runs('ticket')) await checkTicketPrices(browser, base, full);
    if (runs('states')) await checkStates(browser, base, full);
    if (runs('grading')) await checkGradingHistory(browser, base);
    if (runs('reader')) await checkReaderCommentary(browser, base);
    if (runs('inputs')) await checkInputCoverage(browser, base);
  } finally {
    await browser.close();
    server.close();
  }
  console.log(`\n${checks - failures}/${checks} page checks passed${shotsDir ? '; screenshots in ' + shotsDir : ''}`);
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
