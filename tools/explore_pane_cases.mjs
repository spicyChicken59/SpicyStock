import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

// Expand the existing pipeline fixture only in memory, at its normal local
// URL. These labelled copies test layout capacity, never a production scan or
// a new publication. The original six Bursts and COIL remain available too.
function paneRecord(shell) {
  const data = structuredClone(shell);
  const copies = (row, prefix, n) => Array.from({ length: n }, (_, i) => ({
    ...structuredClone(row), ticker: prefix + String(i + 1).padStart(3, '0'),
    name: 'Offline scroll test candidate ' + (i + 1), rank: i + 10
  }));
  data.bursts.push(...copies(data.bursts[0], 'TESTB', 40));
  data.watchlist.top.push(...copies(data.watchlist.top[0], 'TESTS', 18));
  return data;
}

const settle = page => page.waitForTimeout(180);
const selected = page => page.locator('#detail-h2').innerText();
const cards = page => page.locator('#pick-list .ss-pick');
const align = page => page.evaluate(() => window.scrollTo(0,
  document.querySelector('#workspace').getBoundingClientRect().top + scrollY - 16));

// Read the actual screen rectangles and native scroll offsets, without any
// locator action that could scroll a target into view and hide the defect.
async function bounds(page) {
  return page.evaluate(() => {
    const rect = node => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height,
        clientHeight: node.clientHeight, scrollHeight: node.scrollHeight,
        scrollTop: node.scrollTop, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth,
        scrollLeft: node.scrollLeft, overflowY: getComputedStyle(node).overflowY };
    };
    return { pageY: scrollY, viewport: { width: innerWidth, height: innerHeight },
      documentWidth: document.documentElement.scrollWidth,
      picks: rect(document.querySelector('#picks')), list: rect(document.querySelector('#pick-list')),
      detail: rect(document.querySelector('#detail')), identity: rect(document.querySelector('#detail-h2')),
      primary: rect(document.querySelector('#detail .ss-action--burst, #detail .ss-detail__sub')),
      focused: rect(document.activeElement), selectedCard: rect(document.querySelector('#pick-list [aria-pressed="true"]')),
      ticker: document.querySelector('#detail-h2')?.textContent };
  });
}
const near = (a, b) => Math.abs(a - b) <= 2;
const inside = (r, parent, height, pad = 0) => r && parent && r.top >= Math.max(0, parent.top) + pad - 2
  && r.bottom <= Math.min(height, parent.bottom) - pad + 2;

export async function checkExplorePanes({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- Explore panes: labelled offline candidates, normal-origin native scrolling');
  const record = paneRecord(data), metrics = { evidenceKind: 'in-memory expansion of tests/fixtures/page/full.json; normal-origin Chromium; no live-site claim', journeys: [] };
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const launch = (width, height, theme, stage = 'bursts', ticker = stage === 'bursts' ? 'AAPL' : 'COIL') => open(browser, base,
    '/tests/fixtures/page/full.json', '2026-09-10T22:31:00Z', width,
    { height, theme, lens: 'all', hash: '#/explore/' + stage + '/' + ticker, reducedMotion: 'reduce',
      beforeLoad: async page => {
        await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
        await page.route('**/tests/fixtures/page/full.json', route => route.fulfill({ json: record }));
      } });
  const shot = async (page, name) => {
    if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'panes-' + name + '.png') });
  };

  for (const [width, height] of [[1440, 1000], [1280, 800]]) for (const stage of ['bursts', 'setting-up']) for (const theme of ['dark', 'light']) {
    const tag = `${stage}-${width}x${height}-${theme}`, session = await launch(width, height, theme, stage), { page } = session;
    await align(page); await settle(page);
    const initial = await bounds(page), original = await selected(page);
    const total = await cards(page).count();
    check(tag + ': long fixture population is fully rendered', total === (stage === 'bursts' ? 46 : 19), total);
    check(tag + ': matching outer pane tops and bottoms', near(initial.picks.top, initial.detail.top) && near(initial.picks.bottom, initial.detail.bottom), initial);
    check(tag + ': panes fit a comfortable viewport height', initial.picks.height >= height * .5 && initial.picks.height < height, initial);
    check(tag + ': list has real vertical scroll capacity', initial.list.scrollHeight > initial.list.clientHeight + 500, initial.list);
    check(tag + ': details have one native scroll region', initial.detail.scrollHeight > initial.detail.clientHeight && initial.detail.overflowY === 'auto', initial.detail);
    await page.mouse.move(initial.list.left + 60, initial.list.top + 60);
    await page.mouse.wheel(0, 650); await settle(page);
    const wheel = await bounds(page);
    check(tag + ': native wheel scrolls the card region', wheel.list.scrollTop > initial.list.scrollTop + 100, wheel);
    check(tag + ': wheel leaves page and detail screen position stable', near(wheel.pageY, initial.pageY) && near(wheel.detail.top, initial.detail.top), wheel);
    // Reset only the test starting position, then use the actual keyboard.
    await align(page);
    await cards(page).first().focus();
    await page.keyboard.press('End'); await settle(page);
    const end = await bounds(page);
    eq(tag + ': End moves focus without selecting', await selected(page), original);
    const last = await cards(page).last().getAttribute('data-ticker');
    eq(tag + ': End reaches the actual final card', await page.evaluate(() => document.activeElement.dataset.ticker), last);
    await page.keyboard.press('Enter'); await settle(page);
    const late = await bounds(page);
    // PAGE VIEWPORT, immediately after Enter, before any detail locator action.
    await shot(page, tag + '-late');
    eq(tag + ': Enter selects the final candidate', late.ticker, last);
    check(tag + ': late card is visible inside the list', inside(late.selectedCard, late.list, height), late);
    check(tag + ': matching identity is visible beside the list', inside(late.identity, late.detail, height), late);
    check(tag + ': primary header content is visible beside the list', inside(late.primary, late.detail, height), late);
    check(tag + ': End and Enter leave the page at the workspace', near(late.pageY, initial.pageY), { initial, end, late });
    check(tag + ': no document horizontal overflow', late.documentWidth <= width, late);
    metrics.journeys.push({ tag, total, initial, wheel, end, late });
    eq(tag + ': no unexpected browser errors', [...session.errors], []);
    await session.context.close();
  }
  if (shotsDir) await writeFile(path.join(shotsDir, 'explore-pane-metrics.json'), JSON.stringify(metrics, null, 2) + '\n');
}
