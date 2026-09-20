/* The Method view's walkthrough (docs/app-method.js), read back through a real
   browser: it stands on every page, record or none; it steps by button, index,
   keyboard and Play; each step reveals the bars it says and names its module;
   the ticket and the R it prints are the numbers the module declares (which
   tests/test_walkthrough.py holds to Python); the phone stacks it with nothing
   scrolling sideways. Judged against SCStock.walkthrough's own STEPS and
   EXAMPLE, never against the page's prose. */
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const NOW = '2026-09-10T22:31:00Z';
const settle = (p, ms) => p.waitForTimeout(ms || 150);
const txt = (p, sel) => p.locator(sel).first().innerText();
const live = (p) => p.locator('#walkthrough .ss-walk__bar:not(.is-ghost)').count();
const stepOf = (p) => p.evaluate(() => Number(document.querySelector('#walkthrough [data-walk-root]').getAttribute('data-step')));
const sideways = (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
const usd = (v) => '$' + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

export async function checkWalkthrough({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- walkthrough: the method, one burst at a time');
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  // the Play interval is injected the way the page's clock is, so a test does not wait six seconds a step
  const fast = (page) => page.addInitScript(() => { window.SCStock = Object.assign(window.SCStock || {}, { walkthroughInterval: 250 }); });
  const load = (dataUrl, width, extras) => open(browser, base, dataUrl, NOW, width,
    Object.assign({ lens: 'all', hash: '#/method/walkthrough', reducedMotion: 'reduce', beforeLoad: fast }, extras || {}));

  const f = await load('/tests/fixtures/page/full.json', 1280);
  const p = f.page;
  const W = await p.evaluate(() => ({ steps: SCStock.walkthrough.STEPS.map((s) => ({ id: s.id, reveal: s.reveal, title: s.title, module: s.module, days: s.days })),
    bars: SCStock.walkthrough.BARS.length, burst: SCStock.walkthrough.BURST, x: SCStock.walkthrough.EXAMPLE, rules: SCStock.walkthrough.RULES }));
  eq('the walkthrough route opens the Method view and keeps its path', await p.evaluate(() => [location.hash, document.documentElement.getAttribute('data-ss-view')]), ['#/method/walkthrough', 'method']);
  check('the route scrolls the walkthrough onto the screen', await p.evaluate(() => { const r = document.querySelector('#walkthrough').getBoundingClientRect(); return r.top > -2 && r.top < innerHeight / 2; }));
  eq('every synthetic bar is drawn', await p.locator('#walkthrough .ss-walk__bar').count(), W.bars);
  eq('step 1 reveals what its step says', await live(p), W.steps[0].reveal);
  eq('the caption opens on the thesis', await txt(p, '#walkthrough [data-walk="title"]'), W.steps[0].title);
  eq('the count says where the reader is', await txt(p, '#walkthrough [data-walk="count"]'), 'Step 1 of ' + W.steps.length);
  eq('Back is refused on the first step', await p.locator('#walkthrough [data-walk="back"]').getAttribute('aria-disabled'), 'true');
  eq('the chart is one image for assistive technology', await p.locator('#walkthrough svg[role="img"][aria-labelledby]').count(), 1);
  check('the chart is drawn at its own column\'s width, not scaled down into it', await p.evaluate(() => { const s = document.querySelector('#walkthrough svg'), c = s.parentElement.getBoundingClientRect(); return Math.abs(+s.getAttribute('width') - c.width) <= 2 && Math.abs(s.getBoundingClientRect().height - +s.getAttribute('height')) <= 2; }));
  check('on a desktop the caption sits under the chart, beside the step list', await p.evaluate(() => { const r = (x) => document.querySelector('#walkthrough ' + x).getBoundingClientRect(); return r('.ss-walk__caption').top >= r('.ss-walk__stage').bottom - 1 && r('.ss-walk__caption').right <= r('.ss-walk__side').left && r('.ss-walk__side').top < r('.ss-walk__stage').bottom; }));
  // the numbers it quotes are the record's own rules wherever the two name the same constant
  const shared = await p.evaluate((rules) => {
    const rec = SCStock.data.rules || {}, out = {};
    Object.keys(rules).forEach((k) => { const [m, n] = k.split('.'); if (rec[m] && n in rec[m]) out[k] = [rules[k], rec[m][n]]; });
    return out;
  }, W.rules);
  check('the fixture record archives the same rules the walkthrough quotes', Object.keys(shared).length >= 20 && Object.values(shared).every(([a, b]) => a === b), JSON.stringify(shared));

  // by button: each step reveals what it says, names its module, is current in the index
  for (let i = 1; i < W.steps.length; i++) {
    await p.locator('#walkthrough [data-walk="next"]').click(); await settle(p, 100);
    eq(`step ${i + 1} reveals ${W.steps[i].reveal} bars`, await live(p), W.steps[i].reveal);
    eq(`step ${i + 1} names its module`, await p.locator('#walkthrough [data-module][aria-current="true"]').getAttribute('data-module'), W.steps[i].module);
    eq(`step ${i + 1} is current in the index`, await p.locator('#walkthrough [data-walk-step][aria-current="step"]').getAttribute('data-walk-step'), W.steps[i].id);
    eq(`step ${i + 1} titles its caption`, await txt(p, '#walkthrough [data-walk="title"]'), W.steps[i].title);
  }
  eq('Next is refused on the last step', await p.locator('#walkthrough [data-walk="next"]').getAttribute('aria-disabled'), 'true');
  eq('the last step keeps every bar live', await live(p), W.bars);
  const x = W.x;
  const recordFacts = await txt(p, '#walkthrough [data-walk="facts"]');
  check('the record step prints the R the replay wrote', recordFacts.includes((x.r > 0 ? '+' : '') + x.r.toFixed(2) + 'R') && recordFacts.includes('settled on day ' + x.settled_day), recordFacts);
  check('and the two sales it weights', recordFacts.includes(x.sell_half_shares + ' sold at ' + usd(x.sell_half_price)) && recordFacts.includes(x.exit_shares + ' at ' + usd(x.exit_price)), recordFacts);
  eq('the record step labels the R on the chart', await p.locator('#walkthrough [data-mark="r"].is-on').count(), 1);
  const stopPath = await p.locator('#walkthrough [data-mark="stop"] path').getAttribute('d');
  check('the stop path is drawn through all five sessions', /^M[\d.]+,[\d.]+(H[\d.]+|V[\d.]+)+$/.test(stopPath) && (stopPath.match(/V/g) || []).length >= 4, stopPath);

  // the index reaches a step directly, and the plan step prints the ticket the code wrote
  const planIndex = W.steps.findIndex((s) => s.id === 'plan');
  await p.locator('#walkthrough [data-walk-step="plan"]').click(); await settle(p, 100);
  eq('the index takes the reader to the plan', await stepOf(p), planIndex + 1);
  const planText = (await txt(p, '#walkthrough [data-walk="text"]')) + '\n' + (await txt(p, '#walkthrough [data-walk="facts"]'));
  for (const [what, value] of [['trigger', x.trigger], ['limit', x.limit], ['stop', x.stop], ['skip line', x.skip_below], ['day-2 line', x.day2_spent_above], ['position', x.position_usd]])
    check(`the plan step prints the ${what} the plan wrote`, planText.includes(usd(value)), [what, usd(value), planText.slice(0, 200)]);
  check('the plan step prints the share count and the halved budget', planText.includes(x.shares + ' shares') && planText.includes('halved to ' + usd(x.budget_usd)), planText);
  eq('the plan step draws every level in the gutter', (await p.locator('#walkthrough .ss-walk__gutter [data-label]').evaluateAll((e) => e.map((n) => n.dataset.label))).sort(), ['day2', 'limit', 'skip', 'stop', 'trigger']);
  const labels = await p.locator('#walkthrough .ss-walk__gutter text').evaluateAll((e) => e.map((n) => ({ y: +n.getAttribute('y'), text: n.textContent })));
  check('the gutter labels are spread apart', labels.every((l, i) => i === 0 || l.y - labels[i - 1].y >= 13.5), JSON.stringify(labels));
  check('the gutter names the prices', labels.some((l) => l.text.includes(usd(x.limit))) && labels.some((l) => l.text.includes(usd(x.stop))), JSON.stringify(labels));
  eq('the plan step draws no stop path yet', await p.locator('#walkthrough [data-mark="stop"] path').getAttribute('d'), '');
  if (shotsDir) await p.locator('#walkthrough').screenshot({ path: path.join(shotsDir, 'walkthrough-plan-1280-dark.png') });

  // the keyboard on the stage: arrows, Home, End, and Space to play
  await p.locator('#walkthrough .ss-walk__stage').focus();
  await p.keyboard.press('ArrowRight'); await settle(p, 100);
  eq('ArrowRight steps forward', await stepOf(p), planIndex + 2);
  await p.keyboard.press('ArrowLeft'); await settle(p, 100);
  eq('ArrowLeft steps back', await stepOf(p), planIndex + 1);
  await p.keyboard.press('End'); await settle(p, 100);
  eq('End goes to the record', await stepOf(p), W.steps.length);
  await p.keyboard.press('Home'); await settle(p, 100);
  eq('Home goes to the thesis', await stepOf(p), 1);
  await p.keyboard.press(' '); await settle(p, 650);
  check('Space plays from the stage', (await txt(p, '#walkthrough [data-walk="play"]')) === 'Pause' && (await stepOf(p)) >= 2, await stepOf(p));
  await p.locator('#walkthrough [data-walk="play"]').click();
  const paused = await stepOf(p); await settle(p, 600);
  eq('Pause holds the step', await stepOf(p), paused);
  eq('Pause reads Play again', await txt(p, '#walkthrough [data-walk="play"]'), 'Play');
  await p.locator('#walkthrough [data-walk-step="record"]').click(); await settle(p, 100);
  await p.locator('#walkthrough [data-walk="play"]').click(); await settle(p, 120);
  eq('Play from the last step starts over', await stepOf(p), 1);
  await p.locator('#walkthrough [data-walk="play"]').click();
  // the table twin: every bar, the burst marked, readable without the picture
  eq('the chart owes a table twin with every bar', await p.locator('#walkthrough [data-walk="table"] tbody tr').count(), W.bars);
  eq('the twin marks the burst', await p.locator('#walkthrough [data-walk="table"] tbody tr[data-burst]').count(), 1);
  eq('the deep link and the tab open no dialog', await p.locator('dialog[open]').count(), 0);
  eq('walkthrough page errors', f.errors, []);
  await f.context.close();

  // motion on: the reveal staggers, and a reader who steps back gets no stagger
  const m = await load('/tests/fixtures/page/full.json', 1280, { reducedMotion: 'no-preference' });
  await m.page.locator('#walkthrough [data-walk-step="base"]').click();
  const delays = await m.page.locator('#walkthrough .ss-walk__bar').evaluateAll((e) => e.map((n) => n.style.transitionDelay));
  check('a forward step staggers the bars it reveals', delays[0] === '0ms' && delays[5] === '300ms' && delays[W.burst] === '0ms', JSON.stringify(delays));
  eq('motion page errors', m.errors, []);
  await m.context.close();

  // no record at all: the walkthrough still stands and steps
  const none = await load('/tests/fixtures/page/does-not-exist.json', 1280);
  eq('with no record the page says so', await none.page.getAttribute('html', 'data-ss-rendered'), 'error');
  eq('and the walkthrough still draws every bar', await none.page.locator('#walkthrough .ss-walk__bar').count(), W.bars);
  await none.page.locator('#walkthrough [data-walk="next"]').click(); await settle(none.page, 100);
  eq('and still steps', await live(none.page), W.steps[1].reveal);
  // the one failed request on this page is the record that does not exist, which is the point
  eq('no-record walkthrough errors', none.errors.filter((e) => !/404/.test(e)), []);
  await none.context.close();

  // a phone and a narrow phone: stacked, every step readable, nothing sideways
  for (const width of [390, 320]) {
    const n = await load('/tests/fixtures/page/full.json', width, { height: 844 });
    const q = n.page;
    check(`${width}: the chart fits its column`, await q.evaluate(() => { const s = document.querySelector('#walkthrough svg'), c = document.querySelector('#walkthrough .ss-walk__chart'); return s.getBoundingClientRect().width <= c.getBoundingClientRect().width + 1; }));
    check(`${width}: the steps stack under the chart and the caption under them`, await q.evaluate(() => { const r = (s) => document.querySelector('#walkthrough ' + s).getBoundingClientRect(); return r('.ss-walk__side').top >= r('.ss-walk__stage').bottom - 1 && r('.ss-walk__caption').top >= r('.ss-walk__side').bottom - 1; }));
    for (const id of ['plan', 'fill', 'record']) {
      await q.locator(`#walkthrough [data-walk-step="${id}"]`).click(); await settle(q, 100);
      check(`${width}: ${id} scrolls nothing sideways`, !(await sideways(q)));
      check(`${width}: ${id} keeps its gutter labels inside the chart`, await q.evaluate(() => { const s = document.querySelector('#walkthrough svg').getBoundingClientRect(); return Array.from(document.querySelectorAll('#walkthrough .ss-walk__gutter text')).every((t) => t.getBoundingClientRect().right <= s.right + 1); }));
      if (shotsDir && width === 390 && id === 'fill') await q.locator('#walkthrough').screenshot({ path: path.join(shotsDir, 'walkthrough-fill-390-dark.png') });
    }
    eq(`${width}: walkthrough errors`, n.errors, []);
    await n.context.close();
  }
  if (shotsDir) {
    const l = await load('/tests/fixtures/page/full.json', 1280, { theme: 'light' });
    await l.page.locator('#walkthrough [data-walk-step="record"]').click(); await settle(l.page, 100);
    await l.page.locator('#walkthrough').screenshot({ path: path.join(shotsDir, 'walkthrough-record-1280-light.png') });
    eq('light walkthrough errors', l.errors, []);
    await l.context.close();
  }
}
