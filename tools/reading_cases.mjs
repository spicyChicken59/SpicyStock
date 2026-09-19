import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-10T22:31:00Z';
const settle = p => p.waitForTimeout(180);
const txt = (p, s) => p.locator(s).innerText();
const route = async (p, hash) => { await p.evaluate(h => { location.hash = h; }, hash); await settle(p); };
const checklist = async p => { await p.locator('#disc-checklist').evaluate(n => { n.open = true; }); };
const tile = key => '#disc-checklist [data-check="' + key + '"]';
const box = async p => p.evaluate(() => ({ hash: location.hash, page: scrollY, detail: document.querySelector('#detail').scrollTop, list: document.querySelector('#pick-list').scrollTop }));

export async function checkReading({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- reading: recorded meanings and the complete review journey');
  const mutationAt = process.argv.indexOf('--reading-mutation');
  const mutation = mutationAt >= 0 ? process.argv[mutationAt + 1] : null;
  const source = await readFile(path.join(ROOT, 'docs/app-reading.js'), 'utf8');
  async function load(record = data, width = 1440, extras = {}) {
    const opts = { lens: 'all', reducedMotion: 'reduce', hash: '#/explore/bursts/' + record.bursts[0].ticker, ...extras,
      beforeLoad: async page => {
        await page.route('**/reading-offline.json', r => r.fulfill({ json: record }));
        if (mutation) {
          let body = source;
          if (mutation === 'period') body = body.replace("the prior ${n('volume_avg_sessions')}-session average. Long-base", "the following ${n('volume_avg_sessions')}-session average. Long-base");
          if (mutation === 'threshold') body = body.replace("At least ${p('min_close_pos')} of that low-to-high", 'At least 90% of that low-to-high');
          if (mutation === 'unrelated') body = body.replace('No position predicts returns.', 'Map position does not predict returns.');
          if (body === source) throw new Error('Reading failure-control mutation did not change the served module: ' + mutation);
          await page.route('**/app-reading.js', r => r.fulfill({ contentType: 'text/javascript', body }));
        }
      } };
    return open(browser, base, '/reading-offline.json', extras.now || NOW, width, opts);
  }
  const metrics = [];
  const f = await load(); const p = f.page;
  check('first-screen purpose is visible without opening help', (await txt(p, '.ss-orientation')).includes('short-term momentum setups'));
  check('first-screen first action is visible', (await txt(p, '.ss-orientation')).includes('First check market/data'));
  check('snapshot and account boundaries are visible', /not live prices[\s\S]*places no trades[\s\S]*does not know your holdings/.test(await txt(p, '.ss-orientation')));
  check('candidate inclusion is distinct from a ticket', (await txt(p, '#candidate-guide')).includes('Being listed or A-graded does not mean a ticket is available'));
  check('the report supplies its own measured session', (await txt(p, '[data-fact="data"]')).includes('Thu 10 Sep'));
  await checklist(p);
  check('ordinary close rule uses 80%, separate from A+', (await txt(p, tile('close_near_high') + ' .ss-check__rule')).includes('80%') && !(await txt(p, tile('close_near_high') + ' .ss-check__rule')).includes('90%'));
  check('volume observed value says prior 50-session average', (await txt(p, tile('volume') + ' .ss-check__observed')).includes('prior 50-session average'));
  check('volume criterion excludes the burst from its average', (await txt(p, tile('volume') + ' .ss-check__rule')).includes('(burst excluded)'));
  const original = data.bursts[0].quality.checks.find(c => c.key === 'close_near_high');
  await p.locator(tile('close_near_high') + ' details summary').click();
  check('A+ 90% and partial 70% remain separately inspectable', /90%[\s\S]*70%/.test(await txt(p, tile('close_near_high') + ' details')));
  check('complete recorded threshold remains accessible', (await txt(p, tile('close_near_high') + ' details')).includes(original.threshold));
  check('recorded values are never a native-title-only explanation', (await txt(p, tile('close_near_high') + ' details')).includes(original.display));
  eq('help buttons are never nested in other interactive buttons', await p.locator('button button.ss-help, a button.ss-help').count(), 0);

  // Keyboard/hover help is a nonmodal interactive disclosure, not a tooltip.
  const h = p.locator('#cover-regime [data-help-topic="market"]');
  await h.hover(); await p.locator('#ss-reading-help').waitFor();
  eq('interactive help has region semantics', await p.locator('#ss-reading-help').getAttribute('role'), 'region');
  await p.locator('#ss-reading-help p').hover(); await p.waitForTimeout(350);
  check('hover help remains under the pointer', await p.locator('#ss-reading-help').isVisible());
  check('market help explains that a favourable filter cannot supply a ticket', (await txt(p, '#ss-reading-help')).includes('cannot create a ticket or reopen an expired window'));
  await p.keyboard.press('Escape'); eq('Escape dismisses hover help', await p.locator('#ss-reading-help').count(), 0);
  await p.locator('#search').focus(); await h.focus();
  check('keyboard focus opens the same definition', await p.locator('#ss-reading-help').isVisible());
  eq('focus help does not open a modal', await p.locator('dialog[open]').count(), 0);
  await p.keyboard.press('Escape');

  // Choose -> conditions -> actual evidence Focus/Restore -> Method -> return.
  await p.locator('[data-check-action="consolidation"]').click();
  const geom = await p.locator('#chart-mount .sc-chart--stock').evaluate(n => ({ n: n.geometry().n, height: n.geometry().height, domain: n.geometry().domain }));
  await p.locator('#detail [data-evidence-focus]').click();
  check('reading aid keeps genuine evidence Focus', !!await p.locator('#detail .ss-chart-panel').getAttribute('data-focus'));
  await p.locator('#detail [data-evidence-restore]').click();
  eq('reading aid preserves exact normal chart geometry', await p.locator('#chart-mount .sc-chart--stock').evaluate(n => ({ n: n.geometry().n, height: n.geometry().height, domain: n.geometry().domain })), geom);
  const chartHelp = p.locator('#detail [data-help-topic="chart"]'); await chartHelp.click();
  const before = await box(p);
  await p.locator('#ss-reading-help a').click(); await settle(p);
  eq('help link uses the hash router', await p.evaluate(() => location.hash), '#/method/chart');
  check('the relevant Method definition opens', await p.locator('#read-chart').getAttribute('open') !== null);
  await p.locator('#method-return').click(); await settle(p);
  const back = await box(p); eq('Method returns to the same stock route', back.hash, before.hash);
  check('Method restores page and detail reading position', Math.abs(back.page - before.page) < 2 && Math.abs(back.detail - before.detail) < 2, { before, back });
  eq('return does not reopen stale help', await p.locator('#ss-reading-help').count(), 0);

  // Same route context through Compare's modal top layer, then save and revisit.
  await p.locator('#detail [data-pin]').click();
  await route(p, '#/explore/bursts/' + data.bursts[1].ticker);
  await p.locator('#detail [data-pin]').click();
  await p.locator('#compare-open').click();
  await p.locator('#compare [data-help-topic="compare"]').click();
  check('help is readable inside Compare', await p.locator('#compare #ss-reading-help').isVisible());
  await p.keyboard.press('Escape'); check('Escape closes help without closing Compare', await p.locator('#compare').isVisible());
  await p.locator('#compare [data-help-topic="compare"]').click();
  await p.locator('#ss-reading-help a').click(); await settle(p);
  eq('Compare help reaches its on-site definition', await p.evaluate(() => location.hash), '#/method/compare');
  await p.locator('#method-return').click(); await settle(p);
  check('return restores the comparison', await p.locator('#compare').isVisible());
  await p.locator('#compare-close').click(); await settle(p);
  await p.locator('#detail [data-follow-action="add"]').click(); await settle(p);
  await route(p, '#/setups');
  check('saved destination explains browser-only research', (await txt(p, '#following-hint')).includes('Saved in this browser only'));
  await p.locator('#saved-help button').click();
  check('saved confirmation is not stock approval or execution', /save worked[\s\S]*not a positive assessment[\s\S]*not an order/.test(await txt(p, '#ss-reading-help')));
  await p.keyboard.press('Escape');
  await route(p, '#/explore/bursts/' + data.bursts[1].ticker); await p.reload(); await settle(p);
  eq('reload keeps the selected stock', await txt(p, '#detail-h2'), data.bursts[1].ticker);
  check('reload keeps the saved setup', await p.evaluate(() => SCStock.follow.list().length > 0));
  await route(p, '#/record');
  check('populated public model has a HOLD example', (await txt(p, '#hold-rows')).includes('HOLD'));
  check('HOLD is framed as a model, not ownership', (await txt(p, '#hold-hint')).includes('does not know what you hold'));
  await p.locator('#outcome-help button').click();
  check('outcome help defines HOLD and STOPPED without personal execution', /HOLD means the recorded model[\s\S]*STOPPED means its model stop[\s\S]*do not say what you own/.test(await txt(p, '#ss-reading-help')));
  await route(p, '#/explore/bursts/' + data.bursts[1].ticker);
  eq('route changes dismiss stale help', await p.locator('#ss-reading-help').count(), 0);
  await p.locator('#discover [data-discover="map"]').click(); await settle(p);
  check('map scale meaning is visible', (await txt(p, '#burst-map .ss-map__note')).includes('Equal vertical pixel distances are not equal ratio differences'));
  const mapChoice = data.bursts.at(-1).ticker;
  await p.locator('#burst-map .ss-map__point[data-ticker="' + mapChoice + '"]').click(); await settle(p);
  eq('Map opens the selected stock detail', await txt(p, '#detail-h2'), mapChoice);
  await p.locator('#discover [data-discover="cards"]').click(); await settle(p);
  eq('Cards returns with the same stock', await txt(p, '#detail-h2'), mapChoice);
  eq('reading journey has no browser errors', f.errors.slice(), []); await f.context.close();
  if (mutation) return;

  // Lossless retained checklist excerpt in a labelled offline report shell.
  const excerpt = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/chart-focus/excerpt.json')));
  const recorded = structuredClone(data); recorded.fixture = 'reading-retained-excerpt';
  recorded.bursts = structuredClone(excerpt.bursts); recorded.trades = []; recorded.beyond_cap = []; recorded.closest_miss = null;
  const retained = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/reading/bny.json')));
  const bny = recorded.bursts.find(b => b.ticker === 'BNY'); Object.assign(bny, retained.burst);
  recorded.rules.quality = retained.quality_rules; recorded.run.session = retained.source.session;
  const e = await load(recorded, 1280, { hash: '#/explore/bursts/BNY' });
  await checklist(e.page);
  const cons = await txt(e.page, tile('consolidation'));
  check('failing base shows observed giveback with denominator', cons.includes('54% of the rise from prior-leg low to base high') && cons.includes('giveback ≤ 34%'));
  check('failing base shows tightness and its reference period', cons.includes('1.11× the preceding 60-session average') && cons.includes('range ratio ≤ 1×'));
  check('criterion rationale is visible', cons.includes('Why checked: The method checks whether the pause retained the prior advance'));
  const linear = await txt(e.page, tile('linearity'));
  check('passing linearity shows BOTH observations and the OR rule', linear.includes('ER) 0.23') && linear.includes('R²) 0.8') && linear.includes('ER ≥ 0.4 OR R² ≥ 0.55'));
  eq('stored pass is not inferred from the first measurement', await e.page.locator(tile('linearity')).getAttribute('data-verdict'), 'pass');
  check('green criterion cannot create a ticket', (await txt(e.page, '#detail .ss-action')).includes('No SpicyStock entry'));
  check('absent risk narrative does not promise no risk', (await txt(e.page, '[data-item="risk"]')).includes('No separate stock-risk narrative was recorded') && (await txt(e.page, '[data-item="risk"]')).includes('does not mean no risk'));
  check('waiting reason supplies a next review action', (await txt(e.page, '[data-item="need"]')).includes('Wait for a new published plan'));
  const negative = await txt(e.page, tile('narrow_or_negative'));
  check('a negative prior day can pass with an explicit comparison', negative.includes('-0.29%') && negative.includes('Prior close below its previous close OR range < 2%'));
  await e.page.locator('#detail [data-mode="candles"]').click();
  const priorBar = await e.page.locator('#chart-mount .sc-chart--stock').evaluate(n => n.geometry().bars.find(b => b.date === '2026-09-17'));
  eq('the actual passing-prior-session candle is down and filled', [priorBar.o, priorBar.c, priorBar.candle.up, priorBar.candle.filled], [154.52, 153.02, false, true]);
  check('that filled prior candle is rendered', await e.page.locator('#chart-mount .sc-chart__candle.is-filled').evaluateAll((nodes, x) => nodes.some(n => Math.abs(Number(n.getAttribute('x')) - x) < 0.1), priorBar.candle.x));
  eq('the same negative prior-session criterion is a stored pass', await e.page.locator(tile('narrow_or_negative')).getAttribute('data-verdict'), 'pass');
  check('candle caption explains close/open rather than headline gain', (await txt(e.page, '#detail [data-chart-reading]')).includes('close < open'));
  for (const key of ['two_days', 'linearity', 'young_trend']) {
    eq(key + ' has no invented chart anchor', await e.page.locator(tile(key) + ' [data-check-action]').count(), 0);
    check(key + ' explains the unavailable evidence', (await txt(e.page, tile(key))).includes('no dated anchor was recorded'));
  }
  if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await e.page.locator(tile('consolidation')).scrollIntoViewIfNeeded(); await e.page.screenshot({ path: path.join(shotsDir, 'reading-retained-checklist.png') }); await e.page.locator('body').evaluate(n => { n.style.filter = 'grayscale(1)'; }); await e.page.screenshot({ path: path.join(shotsDir, 'reading-retained-checklist-grayscale.png') }); }
  await e.context.close();

  // Archived versions and incomplete measurements: records are cloned only in memory.
  const altered = structuredClone(data); altered.fixture = 'reading-rule-variant'; altered.app.rules_version = 'offline-rule-variant';
  const q = altered.rules.quality, checks = altered.bursts[0].quality.checks;
  q.re_window = 7; q.re_window_long = 14;
  checks.find(c => c.key === 'range_expansion').threshold = "today's range over the largest of the prior 7 >= 1.0 (A+: also over the prior 14)";
  const vol = checks.find(c => c.key === 'volume'); vol.status = 'UNMEASURED'; vol.pass = false; vol.values = { volume_vs_prior: null, volume_vs_avg50: null, volume_rank_60: null, cv_required: null };
  const close = checks.find(c => c.key === 'close_near_high'); close.status = 'PARTIAL'; close.pass = false; close.marginal = true; close.partial = true; close.values = { close_pos: 0.75, close_above_open: true };
  const unknown = checks.find(c => c.key === 'young_trend'); unknown.threshold = 'future_rule_v9 < 123';
  const a = await load(altered); await checklist(a.page);
  eq('uppercase missing is not failure', await a.page.locator(tile('volume')).getAttribute('data-verdict'), 'not measured');
  check('missing measurement is not zero', (await txt(a.page, tile('volume') + ' .ss-check__observed')).includes('not measured') && !(await txt(a.page, tile('volume') + ' .ss-check__observed')).includes('0×'));
  eq('stored partial is not failure', await a.page.locator(tile('close_near_high')).getAttribute('data-verdict'), 'partial');
  check('partial still shows its actual 75% observation', (await txt(a.page, tile('close_near_high') + ' .ss-check__observed')).includes('75%'));
  check('another record uses its own 7-session rule', (await txt(a.page, tile('range_expansion') + ' .ss-check__rule')).includes('prior 7 sessions'));
  await a.page.locator(tile('range_expansion') + ' details summary').click();
  check('another record keeps separate 14-session A+', (await txt(a.page, tile('range_expansion') + ' details')).includes('prior 14 sessions'));
  check('unknown rule is printed without invented translation', (await txt(a.page, tile('young_trend'))).includes('future_rule_v9 < 123') && (await txt(a.page, tile('young_trend'))).includes('not recognised'));
  await a.context.close();

  const red = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/red.json')));
  const rr = await load(red, 390); check('A-quality with red market still refuses entry', (await txt(rr.page, '#detail .ss-detail__chips')).includes('A') && (await txt(rr.page, '#cover-regime')).includes('RED') && (await txt(rr.page, '#detail .ss-action')).includes('No SpicyStock entry')); await rr.context.close();
  const ended = await load(data, 390, { now: '2026-09-11T14:05:00Z' });
  check('recorded ticket with an expired window is no entry', (await txt(ended.page, '#detail .ss-action')).includes('No SpicyStock entry') && /ended/.test(await txt(ended.page, '#detail .ss-action'))); await ended.context.close();

  // Viewport screenshots precede any detail-targeting action. Text enlargement
  // is browser-rendered CSS zoom; it is not a claim about a human zoom study.
  for (const width of [1440, 1280, 960, 820, 768, 721, 390, 320]) for (const theme of ['dark', 'light']) {
    const { page, context, errors } = await load(data, width, { theme, height: width === 1280 ? 800 : 1000, touch: width < 721 });
    await page.mouse.move(0, 0);
    if (shotsDir) await page.screenshot({ path: path.join(shotsDir, `reading-first-${width}-${theme}.png`) });
    const initial = await page.evaluate(() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect(); return { top: b.top, height: b.height, width: b.width }; }; return { viewport: innerHeight, workspace: r('#workspace'), purpose: r('.ss-orientation'), header: r('.ss-detail__head'), identity: r('.ss-detail__head > div:first-child'), overflow: document.documentElement.scrollWidth > innerWidth + 1 }; });
    metrics.push({ width, theme, ...initial });
    check(`${width}/${theme}: no horizontal overflow`, !initial.overflow);
    check(`${width}/${theme}: orientation remains compact`, initial.purpose.height < (width < 721 ? 180 : 90), initial);
    if (width > 720 && width <= 960) check(`${width}/${theme}: controls leave readable identity width`, initial.identity.width >= 300 && initial.header.height < 290, initial);
    if (width === 390 || width === 1440) {
      const hh = page.locator('#cover-regime [data-help-topic="market"]');
      if (width === 390) await hh.tap(); else await hh.click();
      const pb = await page.locator('#ss-reading-help').boundingBox();
      check(`${width}/${theme}: help stays in viewport`, pb.x >= 0 && pb.x + pb.width <= width && pb.y >= 0 && pb.y + pb.height <= 1000, pb);
      if (shotsDir) await page.screenshot({ path: path.join(shotsDir, `reading-help-${width}-${theme}.png`) });
      await page.locator('#ss-reading-help button').click();
      eq('explicit close returns focus to the trigger', await page.evaluate(() => document.activeElement.dataset.helpTopic), 'market');
      await page.evaluate(() => { document.documentElement.style.zoom = '1.5'; });
      check(`${width}/${theme}: enlarged text keeps horizontal bounds`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await hh.click();
      const zoomHelp = await page.locator('#ss-reading-help').boundingBox();
      check(`${width}/${theme}: enlarged help stays within viewport`, zoomHelp.x >= 0 && zoomHelp.x + zoomHelp.width <= width + 1 && zoomHelp.y >= 0 && zoomHelp.y + zoomHelp.height <= 1001, zoomHelp);
      if (shotsDir) await page.screenshot({ path: path.join(shotsDir, `reading-zoom-${width}-${theme}.png`) });
    }
    eq(`${width}/${theme}: browser errors`, errors.slice(), []); await context.close();
  }
  if (shotsDir) await writeFile(path.join(shotsDir, 'reading-metrics.json'), JSON.stringify(metrics, null, 2));
}
