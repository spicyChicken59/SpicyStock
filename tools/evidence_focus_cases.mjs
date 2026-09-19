import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PANEL = '#detail .ss-chart-panel';
const HOST = '#chart-mount .sc-chart--stock';
const KEY = 'spicystock:chart:v1';
const digest = text => createHash('sha256').update(text).digest('hex');
const excerpt = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/chart-focus/excerpt.json')));

// The report shell is a pipeline fixture; only these chart inputs are a
// lossless excerpt of the pinned publication. This is never a live scan.
function focusRecord(shell, rows = excerpt.bursts) {
  const record = structuredClone(shell);
  record.run.session = excerpt.session; record.run.feed = excerpt.feed;
  record.bursts = structuredClone(rows); record.trades = [];
  record.beyond_cap = []; record.closest_miss = null;
  return record;
}

// Read actual SVG coordinates through its screen transform. A taller empty
// container, changed state attribute or highlight opacity cannot pass this.
async function geometry(page) {
  return page.locator(HOST).evaluate(host => {
    const g = host.geometry(), svg = host.querySelector('.sc-chart__stage > svg');
    const matrix = svg.getScreenCTM(), rect = svg.getBoundingClientRect();
    const rounded = n => Math.round(n * 1e6) / 1e6;
    const pixel = (x, y) => new DOMPoint(x, y).matrixTransform(matrix);
    const candles = [...svg.querySelectorAll('.sc-chart__candle')].map(node => {
      const box = node.getBBox(), p = pixel(box.x + box.width / 2, box.y);
      return { x: rounded(p.x - rect.x), y: rounded(p.y - rect.y), w: rounded(box.width * matrix.a), h: rounded(box.height * matrix.d) };
    }).sort((a, b) => a.x - b.x);
    const edges = [...svg.querySelectorAll('.sc-chart__evidence-edge')].map(node =>
      [node.dataset.edge, pixel(0, Number(node.getAttribute('y1'))).y - rect.y]);
    const edge = Object.fromEntries(edges), mark = g.highlight;
    const scale = mark && edge.high !== undefined && edge.low !== undefined && mark.high > mark.low
      ? (edge.low - edge.high) / (mark.high - mark.low) : null;
    const measured = {
      dates: g.bars.map(b => b.date), domain: g.domain, plot: g.plot,
      width: rect.width, height: rect.height, viewBox: svg.getAttribute('viewBox'),
      slot: candles.length > 1 ? (candles.at(-1).x - candles[0].x) / (candles.length - 1) : null,
      priceScale: g.plot.height / (g.domain.hi - g.domain.lo) * matrix.d,
      candles, levels: [...svg.querySelectorAll('[data-level]')].map(n =>
        [n.dataset.level, n.getAttribute('y1'), n.getAttribute('y2')]),
      prices: { stop: g.stop?.price ?? null, trigger: g.trigger?.price ?? null,
        entryLow: g.entry?.low ?? null, entryHigh: g.entry?.high ?? null },
      burst: g.burst?.date ?? null
    };
    return { measured, evidence: mark ? { from: mark.from, to: mark.to, sessions: mark.sessions,
      low: mark.low, high: mark.high, scale, edges } : null, svg: svg.outerHTML };
  });
}

export async function checkEvidenceFocus({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- evidence focus: pinned BPOP/BNY, actual SVG magnification and normal-origin storage');
  const metrics = { source: excerpt.source, evidenceKind: 'retained chart excerpts in an offline fixture; normal-origin Chromium', journeys: [], edges: [] };
  const record = focusRecord(data);
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const launch = async (input, ticker, width, theme) => open(browser, base, '/tests/fixtures/page/full.json',
    '2026-09-18T23:00:00Z', width, { hash: '#/explore/bursts/' + ticker, lens: 'all', theme,
      touch: width < 600, reducedMotion: 'reduce', beforeLoad: async page => {
        // Every external request is disabled, including optional run-log and fonts.
        await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
        await page.route('**/tests/fixtures/page/full.json', route => route.fulfill({ json: input }));
      } });
  const capture = async (page, name) => {
    await page.mouse.move(0, 0);
    if (shotsDir) await page.locator(PANEL).screenshot({ path: path.join(shotsDir, 'focus-' + name + '.png'),
      style: '.sc-masthead { visibility: hidden; }' });
    await page.mouse.move(0, 0);
    return geometry(page);
  };
  const preference = page => page.evaluate(key => localStorage.getItem(key), KEY);
  const restore = page => page.locator(PANEL + ' [data-evidence-restore]').click();
  const focus = page => page.locator(PANEL + ' [data-evidence-focus]').click();
  const select = (page, key) => page.locator(PANEL + ' .ss-evidence [data-anchor="' + key + '"]').click();
  const close = async (session, tag) => { eq(tag + ': no unexpected browser errors', [...session.errors], []); await session.context.close(); };

  for (const width of [1440, 390, 320]) for (const theme of ['dark', 'light']) {
    for (const row of excerpt.bursts) for (const range of (width === 320 ? ['setup'] : ['setup', '60', '120'])) {
      const tag = `${row.ticker}-${range}-${width}-${theme}`;
      const session = await launch(record, row.ticker, width, theme), page = session.page;
      eq(tag + ': a fresh profile starts without a chart preference', await preference(page), null);
      if (range !== 'setup') {
        await page.locator(PANEL + ' .sc-tab[data-range="' + range + '"]').click();
        eq(tag + ': explicit normal range persists', JSON.parse(await preference(page)).range, range);
      }
      const stored = await preference(page);
      for (const key of ['base', 'burst', 'prior']) {
        const name = tag + '-' + key;
        const unselected = await geometry(page);
        await select(page, key);
        const before = await capture(page, name + '-before');
        eq(name + ': selecting evidence only highlights', before.measured, unselected.measured);
        check(name + ': selected evidence has a real price-pixel scale', before.evidence?.scale > 0);
        await page.locator(PANEL + ' [data-evidence-focus]').focus();
        await page.keyboard.press('Enter');
        const after = await capture(page, name + '-after');
        const horizontal = after.measured.slot / before.measured.slot;
        const vertical = after.evidence.scale / before.evidence.scale;
        check(name + ': explicit focus magnifies evidence by at least 25%', Math.max(horizontal, vertical) >= 1.25,
          { horizontal, vertical, before: before.measured.dates.length, after: after.measured.dates.length });
        check(name + ': focus holds at least 21 actual observations', after.measured.dates.length >= 21);
        check(name + ': selected price bounds remain visible at their actual levels', after.evidence.scale > 0
          && after.measured.domain.lo < after.evidence.low && after.measured.domain.hi > after.evidence.high);
        if (row.ticker === 'BPOP' && range === 'setup' && key === 'base')
          check(name + ': recent base uses a tighter window than Setup', after.measured.dates.length < before.measured.dates.length);
        eq(name + ': focus preserves the selected dates and prices',
          [after.evidence.from, after.evidence.to, after.evidence.low, after.evidence.high],
          [before.evidence.from, before.evidence.to, before.evidence.low, before.evidence.high]);
        const originalDates = row.series.map(b => b.date), first = originalDates.indexOf(after.evidence.from), last = originalDates.indexOf(after.evidence.to);
        eq(name + ': whole selected evidence remains visible', after.evidence.sessions, last - first + 1);
        if (first > 0) check(name + ': context on the available left side', after.measured.dates[0] < after.evidence.from);
        if (last < originalDates.length - 1) check(name + ': context on the available right side', after.measured.dates.at(-1) > after.evidence.to);
        eq(name + ': recorded levels unchanged', after.measured.prices, before.measured.prices);
        eq(name + ': focus leaves stored bytes unchanged', await preference(page), stored);
        const bounds = await page.locator(PANEL).evaluate(panel => ({
          overflow: document.documentElement.scrollWidth > innerWidth,
          actions: [...panel.querySelectorAll('[data-evidence-focus], [data-evidence-restore]')].map(n => {
            const r = n.getBoundingClientRect(); return { height: r.height, left: r.left, right: r.right };
          })
        }));
        check(name + ': no horizontal overflow', !bounds.overflow, bounds);
        check(name + ': focus controls remain inside viewport', bounds.actions.every(r => r.left >= 0 && r.right <= width), bounds);
        if (width < 600) check(name + ': focus controls have 44px touch height', bounds.actions.every(r => r.height >= 44), bounds);
        await focus(page);
        eq(name + ': repeated focus does not compound', (await geometry(page)).measured, after.measured);
        const other = key === 'base' ? 'burst' : 'base';
        await select(page, other);
        eq(name + ': retargeting selection alone does not reframe', (await geometry(page)).measured, after.measured);
        eq(name + ': a different target awaits explicit focus', await page.locator(PANEL + ' [data-evidence-focus]').getAttribute('aria-pressed'), 'false');
        await focus(page);
        eq(name + ': explicit retarget identifies the new evidence', await page.locator(PANEL).getAttribute('data-focus'), other);
        await select(page, key); // return the highlight to the original before Restore
        await page.locator(PANEL + ' [data-evidence-restore]').focus(); await page.keyboard.press('Enter');
        const restored = await geometry(page);
        eq(name + ': Restore recovers exact SVG', restored.svg, before.svg);
        eq(name + ': Restore recovers date window and normal geometry', restored.measured, before.measured);
        eq(name + ': Restore leaves stored bytes unchanged', await preference(page), stored);
        eq(name + ': Restore returns keyboard focus to the evidence control', await page.evaluate(() => document.activeElement.hasAttribute('data-evidence-focus')), true);
        metrics.journeys.push({ name, range, width, theme, key, horizontal, vertical, before: { ...before.measured, evidence: before.evidence, svgSha256: digest(before.svg) },
          after: { ...after.measured, evidence: after.evidence, svgSha256: digest(after.svg) }, restoredSvgSha256: digest(restored.svg), storedBefore: stored, storedAfter: await preference(page) });
        // Reload WHILE focused, with no preference reseed, proves focus is temporary.
        await focus(page); await page.reload({ waitUntil: 'load' });
        await page.waitForSelector(HOST);
        eq(name + ': reload returns the stored normal range', await page.locator(HOST).getAttribute('data-range'), range);
        eq(name + ': reload has no temporary focus', await page.locator(PANEL).getAttribute('data-focus'), '');
        eq(name + ': reload retains exact preference bytes', await preference(page), stored);
        await select(page, key);
        eq(name + ': reload restores the exact selected SVG', (await geometry(page)).svg, before.svg);
        await select(page, key); // clear before the next evidence journey
      }
      await close(session, tag);
    }
  }

  // Constructed edge cases over retained price observations. Target dates are
  // changed only in these offline copies; none is claimed as a published base.
  const original = excerpt.bursts[0], all = original.series;
  for (const [name, from, to, start, end] of [
    ['already-compact', 99, 120, 108, 118], ['long-base', 0, 120, 20, 118],
    ['left-boundary', 0, 120, 0, 8], ['right-boundary', 0, 120, 110, 119],
    ['fewer-than-21', 108, 120, 111, 118], ['older-evidence', 0, 120, 10, 15],
    ['unavailable-date', 0, 120, 0, 8]
  ]) {
    const row = structuredClone(original); row.series = all.slice(from, to);
    const observations = all.slice(start, end + 1);
    row.quality.base = { start: name === 'unavailable-date' ? '1900-01-01' : all[start].date, end: all[end].date,
      low: Math.min(...observations.map(b => b.l)), high: Math.max(...observations.map(b => b.h)), sessions: observations.length };
    const session = await launch(focusRecord(data, [row]), row.ticker, 390, 'dark'), page = session.page;
    await page.locator(PANEL + ' .sc-tab[data-range="60"]').click();
    await select(page, 'base');
    const before = await geometry(page);
    if (name === 'unavailable-date') {
      eq(name + ': no fabricated focus target', await page.locator(PANEL + ' [data-evidence-focus]').count(), 0);
    } else {
      await focus(page); const after = await geometry(page);
      check(name + ': floor uses only available real observations', after.measured.dates.length >= Math.min(21, row.series.length)
        && after.measured.dates.every(date => row.series.some(b => b.date === date)));
      eq(name + ': complete evidence retained', [after.evidence.from, after.evidence.to, after.evidence.sessions], [row.quality.base.start, row.quality.base.end, observations.length]);
      if (name === 'older-evidence') {
        check(name + ': viewport excludes actual signal date', !after.measured.dates.includes(excerpt.session));
        eq(name + ': no false burst on last candle', after.measured.burst, null);
        eq(name + ': no false SVG burst mark', await page.locator(HOST + ' .sc-chart__candle--burst, ' + HOST + ' .sc-chart__flag').count(), 0);
      }
      if (shotsDir) await capture(page, 'edge-' + name);
      await restore(page); eq(name + ': exact Restore', (await geometry(page)).svg, before.svg);
      metrics.edges.push({ name, before: before.measured, after: after.measured });
    }
    await close(session, name);
  }
  if (shotsDir) await writeFile(path.join(shotsDir, 'evidence-focus-measurements.json'), JSON.stringify(metrics, null, 2) + '\n');
}

// Fast deterministic geometry reproduction with the actual app and renderer.
// JSDOM supplies controls, not layout: these numbers are NOT visual acceptance.
if (process.argv.includes('--dom')) {
  const { JSDOM, VirtualConsole } = await import('jsdom');
  const shell = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/full.json')));
  let failures = 0;
  for (const width of [1440, 390]) for (const row of excerpt.bursts) {
    const dom = new JSDOM(await readFile(path.join(ROOT, 'docs/index.html'), 'utf8'), {
      url: 'https://focus.test/docs/index.html#/explore/bursts/' + row.ticker,
      runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: new VirtualConsole()
    });
    const w = dom.window;
    Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', { get: () => width < 600 ? 310 : 840 });
    w.matchMedia = query => ({ matches: /max-width/.test(query) && width < 600, addListener() {}, addEventListener() {} });
    w.ResizeObserver = class { observe() {} disconnect() {} }; w.IntersectionObserver = w.ResizeObserver;
    w.scrollTo = () => {}; w.HTMLElement.prototype.scrollIntoView = () => {};
    w.SCStock = { now: '2026-09-18T23:00:00Z' };
    w.fetch = async url => ({ ok: !String(url).includes('github'), text: async () => JSON.stringify(focusRecord(shell)), json: async () => ({}) });
    for (const file of ['docs/design-system/sc-charts.js', 'docs/app-chart.js', 'docs/app-map.js', 'docs/app-follow.js', 'docs/app-reading.js', 'docs/app.js']) {
      const override = file === 'docs/app.js' && process.argv.includes('--app') ? process.argv[process.argv.indexOf('--app') + 1] : null;
      w.eval(await readFile(override || path.join(ROOT, file), 'utf8'));
    }
    await new Promise(resolve => setTimeout(resolve, 80));
    const d = w.document, host = d.querySelector(HOST);
    if (!host) throw new Error('Actual app failed to mount ' + row.ticker);
    if (!host.querySelector('.sc-chart__stage > svg')) throw new Error('Actual chart SVG not found');
    d.querySelector(PANEL + ' [data-anchor="base"]').click();
    const before = host.geometry();
    d.querySelector(PANEL + ' [data-evidence-focus]').click();
    const after = host.geometry();
    const horizontal = after.slot / before.slot;
    const vertical = (after.plot.height / (after.domain.hi - after.domain.lo)) / (before.plot.height / (before.domain.hi - before.domain.lo));
    const pass = Math.max(horizontal, vertical) >= 1.25 && (row.ticker !== 'BPOP' || after.n < before.n);
    console.log(JSON.stringify({ status: pass ? 'PASS' : 'FAIL', kind: 'geometry-only', ticker: row.ticker, width, before: before.n, after: after.n, horizontal, vertical }));
    if (!pass) failures++;
    dom.window.close();
  }
  process.exitCode = failures ? 1 : 0;
}
