// Shared browser regression for the component and its real page consumers.
// Native key presses, wheel events and measured column bounds are intentional:
// assigning scrollLeft or dispatching synthetic keydown would miss this defect.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';

async function settle(page) {
  await page.waitForTimeout(100); // allow the browser to start native scrolling
  await page.evaluate(() => new Promise((resolve, reject) => {
    let prior = '', stable = 0, frames = 0;
    function frame() {
      const next = JSON.stringify([scrollX, scrollY, ...Array.from(document.querySelectorAll('.sc-table-scroll'), s => [s.scrollLeft, s.scrollTop])]);
      stable = next === prior ? stable + 1 : 0; prior = next;
      if (stable >= 8) resolve();
      else if (++frames > 180) reject(new Error('native scrolling did not settle'));
      else requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }));
}

async function bounds(scroll) {
  return scroll.evaluate(s => {
    const r = s.getBoundingClientRect(), left = r.left + s.clientLeft, right = left + s.clientWidth;
    const cells = [...s.querySelectorAll('[data-sc-twin=bars] tr > :last-child')].map(c => {
      const b = c.getBoundingClientRect(), sticky = c.parentElement.firstElementChild.getBoundingClientRect();
      return { left: b.left, right: b.right, visible: b.left >= Math.max(left, sticky.right) - 1 && b.right <= right + 1 };
    });
    return { left, right, clientWidth: s.clientWidth, scrollWidth: s.scrollWidth, scrollLeft: s.scrollLeft,
      finalColumnVisible: cells.length > 1 && cells.every(c => c.visible), cells };
  });
}

async function inspection(host) {
  return host.evaluate(h => ({
    cross: h.querySelector('.sc-chart__cross').outerHTML,
    tooltip: h.querySelector('.sc-tooltip').classList.contains('is-on'),
    date: h.querySelector('.sc-tooltip__date')?.textContent || ''
  }));
}

export async function checkChartKeyboard({ page, host, check, tag, shotsDir }) {
  const test = (name, pass, detail) => check(`${tag}: ${name}`, pass, detail);
  const summary = host.locator('.sc-details > summary'), scroll = host.locator('.sc-table-scroll');
  const details = host.locator('.sc-details');
  const shape = () => host.evaluate(h => { const s = h.querySelector('.sc-chart__stage > svg').cloneNode(true); s.querySelector('.sc-chart__cross').remove(); return s.outerHTML; });
  const beforeShape = await shape(), route = await page.evaluate(() => location.hash);
  await page.mouse.move(0, 0);
  await host.focus();
  // Controls still exercise the host, including the two edge keys.
  for (const [key, offset] of [['Home', 0], ['ArrowRight', 1], ['End', -1], ['ArrowLeft', -2]]) {
    await page.keyboard.press(key);
    test(`chart host ${key} inspects the expected session`, await host.evaluate((h, offset) => {
      const g = h.geometry(), i = offset < 0 ? g.n + offset : offset;
      return h.querySelector('.sc-tooltip').classList.contains('is-on') && h.querySelector('.sc-tooltip__date').textContent.endsWith(g.bars[i].date);
    }, offset));
  }
  await page.keyboard.press('Escape');
  test('chart host Escape clears inspection', await host.evaluate(h => !h.querySelector('.sc-tooltip').classList.contains('is-on') && h.querySelector('.sc-chart__cross').getAttribute('visibility') === 'hidden'));
  await page.keyboard.press('Tab');
  test('Tab reaches disclosure from the chart', await summary.evaluate(s => s === document.activeElement));
  if (await details.evaluate(d => d.open)) await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  test('Enter opens the native disclosure', await details.evaluate(d => d.open));
  await page.keyboard.press('Tab');
  const reachable = await scroll.evaluate(s => s === document.activeElement);
  test('Tab reaches the table scroller', reachable);
  test('scroller has an explicit tab stop and meaningful region name', await scroll.evaluate(s => s.getAttribute('tabindex') === '0' && s.getAttribute('role') === 'region' && /.+: last 10 sessions and chart levels/.test(s.getAttribute('aria-label') || '')));
  test('native table captions and column headers remain', await scroll.evaluate(s => s.querySelectorAll('table').length === 2 && s.querySelectorAll('caption').length === 2 && s.querySelectorAll('[data-sc-twin=bars] thead th').length === 7 && [...s.querySelectorAll('table')].every(t => !t.hasAttribute('role'))));
  if (!reachable) return; // retain the useful assertion if a focusability mutant removes the stop
  test('keyboard focus has a visible outline', await scroll.evaluate(s => s.matches(':focus-visible') && parseFloat(getComputedStyle(s).outlineWidth) >= 2 && getComputedStyle(s).outlineStyle !== 'none'));
  await settle(page);
  const unchanged = JSON.stringify(await inspection(host));
  await scroll.evaluate(s => { s.__keys = []; s.__capture = e => s.__keys.push({ key: e.key, prevented: e.defaultPrevented }); document.addEventListener('keydown', s.__capture); });
  const initial = await bounds(scroll), overflowing = initial.scrollWidth > initial.clientWidth + 1;
  const take = async suffix => { if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await host.screenshot({ path: path.join(shotsDir, `${tag}-${suffix}.png`) }); await scroll.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(shotsDir, `${tag}-${suffix}-viewport.png`) }); } };
  await take('left');
  let right = initial;
  // Even a nonoverflowing desktop table must retain ownership of its keys.
  for (let i = 0; i < 24; i++) {
    await page.keyboard.press('ArrowRight'); await settle(page); right = await bounds(scroll);
    if (right.finalColumnVisible || right.scrollLeft === initial.scrollLeft) break;
  }
  test('Right Arrow reveals every cell in the final column', right.finalColumnVisible, JSON.stringify(right));
  test('table arrows leave chart inspection unchanged', JSON.stringify(await inspection(host)) === unchanged);
  await take('right');
  for (let i = 0; i < 24; i++) {
    await page.keyboard.press('ArrowLeft'); await settle(page);
    if ((await bounds(scroll)).scrollLeft <= 1) break;
  }
  test('Left Arrow returns to the opening columns', await scroll.evaluate(s => {
    const r = s.getBoundingClientRect(), c = s.querySelector('[data-sc-twin=bars] th:nth-child(2)').getBoundingClientRect();
    return s.scrollLeft <= 1 && c.left >= s.querySelector('th').getBoundingClientRect().right - 1 && c.right <= r.left + s.clientLeft + s.clientWidth + 1;
  }));
  for (const key of ['Home', 'End', 'Escape']) { await page.keyboard.press(key); await settle(page); }
  const trace = await scroll.evaluate(s => { document.removeEventListener('keydown', s.__capture); const keys = s.__keys; delete s.__capture; delete s.__keys; return keys; });
  test('table Left/Right/Home/End/Escape retain native defaults', trace.length >= 5 && trace.every(k => !k.prevented), JSON.stringify(trace));
  test('all table keys leave the tooltip and crosshair unchanged', JSON.stringify(await inspection(host)) === unchanged);
  await page.keyboard.press('Shift+Tab');
  test('Shift+Tab leaves the scroller for its summary', await summary.evaluate(s => s === document.activeElement));
  await page.keyboard.press('Space');
  test('Space closes the native disclosure', await details.evaluate(d => !d.open));
  await page.keyboard.press('Space'); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
  test('Tab exits the table without trapping focus', await host.evaluate(h => !h.contains(document.activeElement)));
  await page.keyboard.press('Shift+Tab');
  test('Shift+Tab returns from the next control', await scroll.evaluate(s => s === document.activeElement));

  // Summary shortcuts are not chart shortcuts either.
  await page.keyboard.press('Shift+Tab');
  const summaryState = JSON.stringify(await inspection(host));
  await summary.evaluate(s => { s.__keys = []; s.__capture = e => s.__keys.push(e.defaultPrevented); document.addEventListener('keydown', s.__capture); });
  for (const key of ['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Escape']) await page.keyboard.press(key);
  const summaryKeys = await summary.evaluate(s => { document.removeEventListener('keydown', s.__capture); const keys = s.__keys; delete s.__capture; delete s.__keys; return keys; });
  test('disclosure keys do not activate or move chart inspection', JSON.stringify(await inspection(host)) === summaryState && summaryKeys.every(p => !p));
  await settle(page);
  await scroll.scrollIntoViewIfNeeded();
  const box = await scroll.boundingBox();
  // The tall table can straddle the viewport after native Home/End.
  await page.mouse.move(box.x + box.width / 2, Math.min(page.viewportSize().height - 30, Math.max(30, box.y + 35)));
  if (overflowing) {
    await page.mouse.wheel(initial.scrollWidth, 0); await settle(page);
    test('pointer scrolling still reveals the final column', (await bounds(scroll)).finalColumnVisible);
    await page.mouse.wheel(-initial.scrollWidth, 0); await settle(page);
    test('pointer scrolling returns left', (await bounds(scroll)).scrollLeft <= 1);
  }
  const y = await page.evaluate(() => scrollY);
  // Explore has its own scroll pane on desktop; mobile uses the document.
  const ancestors = await scroll.evaluate(s => { const out = []; for (let p = s.parentElement; p; p = p.parentElement) out.push(p.scrollTop); return out; });
  await page.mouse.wheel(0, -300); await settle(page);
  const movedAncestor = await scroll.evaluate((s, before) => { let i = 0; for (let p = s.parentElement; p; p = p.parentElement) if (p.scrollTop < before[i++]) return true; return false; }, ancestors);
  test('vertical wheel over the table continues scrolling the surrounding page', await page.evaluate(() => scrollY) < y || movedAncestor);
  test('chart geometry and route/selection are preserved', await shape() === beforeShape && await page.evaluate(() => location.hash) === route);
  if (shotsDir) await writeFile(path.join(shotsDir, `${tag}-bounds.json`), JSON.stringify({ viewport: page.viewportSize(), route, browser: page.context().browser().version(), initial, right, keys: trace }, null, 2));
}

// The retained publication keeps NIC's exact reported journey reproducible
// after automatic publication advances docs/data.json. Other consumers use
// the existing synthetic fixture and a fresh, disposable browser context.
export async function checkPageChartKeyboard({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- chart table keyboard ownership');
  const root = path.resolve(import.meta.dirname, '..');
  const bytes = gunzipSync(await readFile(path.join(root, 'tests/fixtures/chart-keyboard/2026-09-24.json.gz')));
  eq('chart keyboard: exact September 24 publication', createHash('sha256').update(bytes).digest('hex'), '97da76d4f0eae671a5168760b79852c2eb6c4539bef3a144df6ef6bfe20c93f4');
  for (const width of [360, 390, 1280]) for (const theme of ['dark', 'light']) {
    const { page, context, errors } = await open(browser, base, '/chart-keyboard-retained.json', '2026-09-25T05:05:06Z', width, {
      height: width === 390 ? 844 : width === 360 ? 800 : 900, theme, hash: '#/explore/bursts/NIC',
      beforeLoad: async p => {
        await p.route('**/chart-keyboard-retained.json', r => r.fulfill({ contentType: 'application/json', body: bytes }));
        await p.route(/^https?:\/\/(?!127\.0\.0\.1)/, r => r.fulfill({ status: 200, body: '' }));
      }
    });
    try {
      const host = page.locator('#detail .sc-chart--stock');
      eq('NIC chart still names the reported final session', await host.locator('[data-sc-twin=bars] tbody tr').first().locator('td').first().textContent(), '2026-09-24 ▲ burst');
      await checkChartKeyboard({ page, host, check, tag: `NIC-${width}-${theme}`, shotsDir });
      eq('NIC keyboard journey has no browser errors', [...errors], []);
    } finally { await context.close(); }
  }
  for (const width of [390, 1280]) for (const theme of ['dark', 'light']) {
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', '2026-09-10T22:31:00Z', width, {
      height: width === 390 ? 844 : 900, theme, lens: 'all', hash: '#/explore/bursts/AAPL',
      beforeLoad: p => p.route(/^https?:\/\/(?!127\.0\.0\.1)/, r => r.fulfill({ status: 200, body: '' }))
    });
    try {
      async function consumer(selector, tag) {
        const host = page.locator(selector), summary = host.locator('summary'), scroll = host.locator('.sc-table-scroll');
        await host.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Enter'); await page.keyboard.press('Tab');
        check(`${tag}: Tab reaches its named table region`, await scroll.evaluate(s => s === document.activeElement && s.getAttribute('tabindex') === '0' && s.getAttribute('role') === 'region' && !!s.getAttribute('aria-label')));
        const before = await page.locator('.sc-chart--stock').evaluateAll(hs => hs.map(h => h.querySelector('.sc-chart__stage > svg').outerHTML));
        const initial = await bounds(scroll);
        let right = initial;
        for (let i = 0; i < 24; i++) { await page.keyboard.press('ArrowRight'); await settle(page); right = await bounds(scroll); if (right.finalColumnVisible || right.scrollLeft === initial.scrollLeft) break; }
        check(`${tag}: keyboard reveals final column inside its scroller`, right.finalColumnVisible, JSON.stringify(right));
        if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await scroll.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(shotsDir, `${tag}-right-viewport.png`) }); }
        for (let i = 0; i < 24; i++) { await page.keyboard.press('ArrowLeft'); await settle(page); if ((await bounds(scroll)).scrollLeft <= 1) break; }
        check(`${tag}: keyboard returns left`, (await bounds(scroll)).scrollLeft <= 1);
        eq(`${tag}: neither chart inspection nor its peer changes`, await page.locator('.sc-chart--stock').evaluateAll(hs => hs.map(h => h.querySelector('.sc-chart__stage > svg').outerHTML)), before);
        await page.keyboard.press('Shift+Tab');
        check(`${tag}: Shift+Tab exits to disclosure`, await summary.evaluate(s => s === document.activeElement));
        await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
        check(`${tag}: Tab exits table`, await host.evaluate(h => !h.contains(document.activeElement)));
        await page.keyboard.press('Shift+Tab');
        check(`${tag}: Shift+Tab returns to table`, await scroll.evaluate(s => s === document.activeElement));
        if (shotsDir) { await scroll.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(shotsDir, `${tag}-left-viewport.png`) }); }
      }
      // Save through the UI into this context only, preserving its frozen bars.
      await page.locator('#detail [data-follow-action="add"]').click();
      await page.waitForFunction(() => SCStock.follow.list().length === 1);
      const savedBefore = await page.evaluate(() => JSON.stringify(SCStock.follow.list()));
      await page.locator('#detail [data-pin]').click();
      await page.locator('#pick-list .ss-pick[data-ticker="AMD"]').click();
      await page.locator('#detail [data-pin]').click();
      const route = await page.evaluate(() => location.hash);
      await page.locator('#compare-open').click();
      await consumer('#cmp-a-mount .sc-chart--stock', `comparison-a-${width}-${theme}`);
      if (width < 600) await page.locator('#compare [data-ab="b"]').click();
      await consumer('#cmp-b-mount .sc-chart--stock', `comparison-b-${width}-${theme}`);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('compare').open);
      eq('table Escape retains native comparison dismissal and focus return', await page.evaluate(() => document.activeElement.id), 'compare-open');
      eq('comparison leaves selected stock unchanged', await page.evaluate(() => location.hash), route);
      await page.locator('#nav [data-view="setups"]').click();
      await page.locator('#following [data-open-saved]').first().click();
      await consumer('#saved .sc-chart--stock', `saved-${width}-${theme}`);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('saved').open);
      check('keyboard inspection preserves the disposable saved snapshot', await page.evaluate(() => JSON.stringify(SCStock.follow.list())) === savedBefore);
      eq('shared chart consumers have no browser errors', [...errors], []);
    } finally { await context.close(); }
  }
}
