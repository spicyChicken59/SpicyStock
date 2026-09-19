import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

// Expand the existing pipeline fixture only in memory, at its normal local
// URL. These labelled copies test layout capacity, never a production scan or
// a new publication. The original six Bursts and COIL remain available too.
function paneRecord(shell) {
  const data = structuredClone(shell);
  const copies = (row, prefix, n) => Array.from({ length: n }, (_, i) => ({
    ...structuredClone(row), ticker: prefix + String(i + 1).padStart(3, '0'),
    name: 'Offline scroll test candidate ' + (i + 1) + (i < 2 ? ' SHORTPAIR' : ''), rank: i + 10
  }));
  data.bursts.push(...copies(data.bursts[0], 'TESTB', 40));
  data.watchlist.top.push(...copies(data.watchlist.top[0], 'TESTS', 18));
  for (const row of [data.bursts.at(-3), data.watchlist.top.at(-3)]) { row.series = []; delete row.evidence; }
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
      header: rect(document.querySelector('.ss-detail__head')),
      identityBlock: rect(document.querySelector('.ss-detail__head > div:first-child')),
      search: rect(document.querySelector('#search')), lens: rect(document.querySelector('#lens')),
      primary: rect(document.querySelector('#detail .ss-action--burst') || document.querySelector('#detail .ss-detail__sub')),
      focused: rect(document.activeElement), selectedCard: rect(document.querySelector('#pick-list [aria-pressed="true"]')),
      ticker: document.querySelector('#detail-h2')?.textContent };
  });
}
const near = (a, b) => Math.abs(a - b) <= 2;
const inside = (r, parent, height, pad = 0) => r && parent && r.top >= Math.max(0, parent.top) + pad - 2
  && r.bottom <= Math.min(height, parent.bottom) - pad + 2;

export async function checkExplorePanes({ browser, base, data, open, check, eq, shotsDir }) {
  console.log('-- Explore panes: labelled offline candidates, normal-origin native scrolling');
  const report = check;
  check = (name, ok, detail) => report(name, ok, detail && typeof detail === 'object' ? JSON.stringify(detail) : detail);
  const record = paneRecord(data), metrics = { evidenceKind: 'in-memory expansion of tests/fixtures/page/full.json; normal-origin Chromium; no live-site claim', journeys: [] };
  if (shotsDir) await mkdir(shotsDir, { recursive: true });
  const saveMetrics = async () => { if (shotsDir) await writeFile(path.join(shotsDir, 'explore-pane-metrics.json'), JSON.stringify(metrics, null, 2) + '\n'); };
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
  const go = async (page, stage, ticker) => {
    await page.evaluate(h => SCStock.navigate(h), '#/explore/' + stage + '/' + ticker); await settle(page);
  };
  const visibleSelected = async (page, tag) => {
    const b = await bounds(page);
    check(tag + ': selected card remains discoverable', inside(b.selectedCard, b.list, b.viewport.height), b);
  };
  const interactions = async (page, stage, tag, late, total) => {
    const height = late.viewport.height, last = late.ticker, prefix = stage === 'bursts' ? 'TESTB' : 'TESTS';
    const beforeDeep = await bounds(page);
    await page.mouse.move(late.detail.left + 100, late.detail.top + 240);
    await page.mouse.wheel(0, 800); await settle(page);
    const deep = await bounds(page);
    check(tag + ': native detail wheel exposes lower content', deep.detail.scrollTop > 300, deep);
    check(tag + ': detail scrolling preserves list and page', near(deep.list.scrollTop, beforeDeep.list.scrollTop) && near(deep.pageY, beforeDeep.pageY), deep);
    await cards(page).last().click(); await settle(page);
    const same = await bounds(page);
    check(tag + ': selecting the same stock preserves detail scroll', near(same.detail.scrollTop, deep.detail.scrollTop), { deep, same });
    // Browse to a fully visible different card first. Clicking a clipped card
    // can legitimately need a nearest-position adjustment; this case isolates
    // the promise to preserve a list position that already exposes the target.
    await page.mouse.move(same.list.left + 60, same.list.top + 60);
    await page.mouse.wheel(0, -650); await settle(page);
    const beforeChoice = await bounds(page);
    const other = await cards(page).evaluateAll(nodes => {
      const list = document.querySelector('#pick-list').getBoundingClientRect();
      return nodes.find(n => { const r = n.closest('.ss-pick-item').getBoundingClientRect();
        return n.getAttribute('aria-pressed') !== 'true' && r.top >= list.top + 4 && r.bottom <= list.bottom - 4;
      })?.dataset.ticker;
    });
    check(tag + ': browsing exposes a different complete card', !!other);
    if (other) await page.locator('#pick-list .ss-pick[data-ticker="' + other + '"]').click();
    await settle(page);
    const changed = await bounds(page);
    check(tag + ': a different stock reveals identity and resets only detail', changed.detail.scrollTop === 0 && inside(changed.identity, changed.detail, height)
      && near(changed.list.scrollTop, beforeChoice.list.scrollTop) && near(changed.pageY, beforeChoice.pageY), { beforeChoice, changed });
    await go(page, stage, prefix + (stage === 'bursts' ? '038' : '016'));
    eq(tag + ': missing chart has a readable unavailable state', await page.locator('#detail [data-chart="unavailable"]').count(), 1);
    await cards(page).last().click(); await settle(page);
    // A browse-only keyboard journey must never select or snap back on rerender.
    await cards(page).last().focus(); await page.keyboard.press('Home'); await settle(page);
    const browsing = await bounds(page);
    await page.evaluate(() => SCStock.navigate(location.hash)); await settle(page);
    const rerender = await bounds(page);
    check(tag + ': same-route rerender preserves an intentional browse position', near(rerender.list.scrollTop, browsing.list.scrollTop), { browsing, rerender });
    for (const key of ['ArrowDown', 'ArrowUp', 'End', 'ArrowUp', 'ArrowDown', 'Home']) {
      await page.keyboard.press(key); await settle(page);
      const b = await bounds(page);
      eq(tag + ': ' + key + ' only moves focus', b.ticker, last);
      check(tag + ': ' + key + ' focus ring fits inside list and viewport', inside(b.focused, b.list, height, 4), b);
      check(tag + ': ' + key + ' leaves outer page stable', near(b.pageY, late.pageY), b);
    }
    await page.keyboard.press('Enter'); await settle(page);
    eq(tag + ': Home then Enter selects the first card', await selected(page), stage === 'bursts' ? 'AAPL' : 'COIL');
    await page.locator('#detail [data-step="next"]').focus(); await page.keyboard.press('Enter'); await settle(page);
    const second = await selected(page);
    await visibleSelected(page, tag + ' Next');
    eq(tag + ': Next retains usable keyboard focus', await page.evaluate(() => document.activeElement.dataset.step), 'next');
    await page.locator('#detail [data-step="prev"]').focus(); await page.keyboard.press('Enter'); await settle(page);
    await visibleSelected(page, tag + ' Previous');
    // Native search keeps the detail while filtering, then Enter chooses.
    const search = page.locator('#search'), prior = await selected(page);
    for (const [query, count] of [['SHORTPAIR', 2], [prefix + '001', 1], ['NO_SUCH_TEST', 0]]) {
      await search.fill(query); await settle(page);
      eq(tag + ': search population ' + query, await cards(page).count(), count);
      eq(tag + ': filtering does not select', await selected(page), prior);
      eq(tag + ': Previous/Next cannot leave a search hiding the current stock',
        await page.locator('#detail [data-step]').evaluateAll(nodes => nodes.every(n => n.disabled)), true);
      const b = await bounds(page);
      check(tag + ': short/single/empty panes retain matching boundaries', near(b.picks.bottom, b.detail.bottom) && near(b.picks.height, late.picks.height), b);
    }
    await search.fill(last); await search.press('Enter'); await settle(page);
    eq(tag + ': search Enter chooses the requested stock', await selected(page), last);
    await visibleSelected(page, tag + ' Search');
    await page.goBack(); await settle(page);
    eq(tag + ': Back restores the previous selection', await selected(page), prior);
    await visibleSelected(page, tag + ' Back');
    await go(page, stage, second); await visibleSelected(page, tag + ' Deep link');
    await search.fill(prefix + '001'); await settle(page);
    await page.goBack(); await settle(page);
    eq(tag + ': Back clears only a search hiding its named stock', await search.inputValue(), '');
    await visibleSelected(page, tag + ' Back through a filter');
    await page.locator('#lens [data-lens="following"]').click(); await settle(page);
    eq(tag + ': empty lens keeps all candidates in the underlying stage', await cards(page).count(), 0);
    eq(tag + ': empty lens explains the missing selection', await page.locator('#detail [data-detail="lens"]').count(), 1);
    await page.locator('#lens [data-lens="all"]').click(); await settle(page);
    eq(tag + ': clearing lens restores the full population', await cards(page).count(), total);
    if (stage === 'bursts') {
      await page.locator('#lens [data-sort="gain"]').click(); await settle(page);
      await visibleSelected(page, tag + ' Gain sort');
      await page.locator('#lens [data-sort="rank"]').click(); await settle(page);
      await visibleSelected(page, tag + ' Rank sort');
    }
    await go(page, stage, stage === 'bursts' ? 'AAPL' : 'COIL');
    await align(page); await settle(page);
    const chartHeight = await page.locator('#chart-mount .sc-chart__stage > svg').evaluate(n => n.getBoundingClientRect().height);
    eq(tag + ': normal chart keeps its 400px drawing height', chartHeight, 400);
    const pageAt = (await bounds(page)).pageY;
    await page.locator('#detail .ss-evidence [data-anchor="' + (stage === 'bursts' ? 'base' : 'box') + '"]').click();
    const focus = page.locator('#detail [data-evidence-focus]');
    await focus.focus(); await page.keyboard.press('Enter'); await settle(page);
    const focused = await bounds(page);
    check(tag + ': Focus evidence keeps keyboard focus visible in the pane', inside(focused.focused, focused.detail, height), focused);
    check(tag + ': Focus evidence does not jump the page', near(focused.pageY, pageAt), focused);
    await shot(page, tag + '-evidence-focus');
    await page.locator('#detail [data-evidence-restore]').focus(); await page.keyboard.press('Enter'); await settle(page);
    const restored = await bounds(page);
    check(tag + ': Restore returns visible keyboard focus within detail', inside(restored.focused, restored.detail, height), restored);
    check(tag + ': Restore does not jump the page', near(restored.pageY, pageAt), restored);
    eq(tag + ': Restore keeps normal chart height', await page.locator('#chart-mount .sc-chart__stage > svg').evaluate(n => n.getBoundingClientRect().height), chartHeight);
    // Native clicks reach every disclosure through the detail's single scroll.
    for (const id of ['checklist', 'plan', 'exits', 'provenance']) {
      await page.locator('#disc-' + id + ' > summary').click(); await settle(page);
      const b = await bounds(page);
      check(tag + ': ' + id + ' disclosure does not move the outer page', near(b.pageY, pageAt), b);
      eq(tag + ': ' + id + ' disclosure is open', await page.locator('#disc-' + id).evaluate(n => n.open), true);
    }
    await page.locator('#detail').focus(); await page.keyboard.press('Control+End'); await settle(page);
    // Use native scrolling to the end; the last content must remain reachable.
    await page.mouse.move(late.detail.left + 100, late.detail.top + 250);
    await page.mouse.wheel(0, 20000); await settle(page);
    const bottom = await bounds(page);
    check(tag + ': detail bottom is reachable', near(bottom.detail.scrollTop + bottom.detail.clientHeight, bottom.detail.scrollHeight), bottom);
    await page.evaluate(() => SCStock.navigate(location.hash)); await settle(page);
    const held = await bounds(page);
    check(tag + ': ordinary detail rerender preserves reading position', near(held.detail.scrollTop, bottom.detail.scrollTop), { bottom, held });
    await shot(page, tag + '-provenance');
    // Tab can leave the last disclosure and reach the surrounding document.
    let escaped = false;
    for (let i = 0; i < 110; i++) {
      await page.keyboard.press('Tab');
      if (await page.evaluate(() => document.activeElement.matches('#orders > summary, #scan > summary'))) { escaped = true; break; }
    }
    check(tag + ': keyboard can leave the detail region for the document', escaped);
    await page.keyboard.press('Shift+Tab');
    check(tag + ': keyboard can reenter detail from the document', await page.evaluate(() => document.querySelector('#detail').contains(document.activeElement)));
    await go(page, stage, last); await align(page); await settle(page);
    await page.locator('#pick-list .ss-pick[aria-pressed="true"]').focus();
    let entered = false;
    for (let i = 0; i < 8; i++) { await page.keyboard.press('Tab'); if (await page.evaluate(() => document.querySelector('#detail').contains(document.activeElement))) { entered = true; break; } }
    check(tag + ': keyboard can leave the final card tools and enter detail', entered);
    metrics.journeys.push({ tag: tag + '-interactions', deep, same, beforeChoice, changed, browsing, rerender, focused, restored, bottom, held });
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
    check(tag + ': search and filters remain visible while cards scroll', inside(wheel.search, wheel.picks, height) && inside(wheel.lens, wheel.picks, height), wheel);
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
    await saveMetrics();
    if (theme === 'dark' && initial.list.scrollHeight > initial.list.clientHeight + 500) await interactions(page, stage, tag, late, total);
    eq(tag + ': no unexpected browser errors', [...session.errors], []);
    await session.context.close();
  }
  // Fresh contexts: deep-link discovery, mobile rail/chooser and both mode
  // boundaries. A page viewport shot is used throughout, never a component shot.
  for (const width of [960, 820, 768, 721, 720, 390, 320]) for (const theme of ['dark', 'light']) {
    const tag = `${width}-${theme}`, session = await launch(width, 900, theme, 'bursts', 'TESTB040'), { page } = session;
    await align(page); await settle(page);
    let b = await bounds(page);
    if (width > 720) {
      await visibleSelected(page, tag + ' fresh deep link');
      check(tag + ': intermediate desktop keeps matching panes', near(b.picks.bottom, b.detail.bottom), b);
      check(tag + ': badges and controls leave readable identity width',
        b.identityBlock.clientWidth >= Math.min(300, b.header.clientWidth) - 2, b);
      check(tag + ': constrained header wraps into intentional rows', b.header.height < 270, b);
    } else {
      check(tag + ': mobile keeps a horizontal card rail', b.list.scrollWidth > b.list.clientWidth && b.list.scrollHeight <= b.list.clientHeight + 2, b);
      check(tag + ': mobile details stay in the stacked page flow', b.detail.top >= b.picks.bottom && b.detail.scrollHeight <= b.detail.clientHeight + 2, b);
      await page.locator('#choose-open').click();
      await page.locator('#chooser-search').fill('TESTB001');
      await page.locator('#chooser-search').press('Enter'); await settle(page);
      b = await bounds(page);
      eq(tag + ': chooser selects and reveals stock identity', b.ticker, 'TESTB001');
      check(tag + ': chooser identity is visible in stacked flow', inside(b.identity, b.detail, 900), b);
      await shot(page, tag + '-chooser');
      const at = b.pageY;
      await page.mouse.move(width / 2, 400); await page.mouse.wheel(0, 450); await settle(page);
      check(tag + ': mobile retains native page scrolling', (await bounds(page)).pageY > at + 100);
      await page.locator('#detail .ss-detail__back').click(); await settle(page);
    }
    await shot(page, tag + '-cards');
    await page.locator('#discover [data-discover="map"]').click(); await settle(page);
    const map = await bounds(page);
    check(tag + ': Map retains full-width unbounded detail', near(map.picks.left, map.detail.left) && near(map.picks.right, map.detail.right)
      && map.detail.scrollHeight <= map.detail.clientHeight + 2, map);
    await page.locator('#discover [data-discover="cards"]').click(); await settle(page);
    await align(page); await settle(page);
    b = await bounds(page);
    check(tag + ': transitions have no horizontal document overflow', b.documentWidth <= width, b);
    if (width > 720) await visibleSelected(page, tag + ' Cards return');
    await shot(page, tag + '-cards-return');
    metrics.journeys.push({ tag, cards: b, map });
    eq(tag + ': no unexpected browser errors', [...session.errors], []);
    await session.context.close();
  }
  const resized = await launch(1440, 1000, 'dark', 'bursts', 'TESTB040'), page = resized.page;
  for (const [width, height] of [[390, 844], [320, 800], [720, 900], [721, 900], [1280, 800], [1440, 1000]]) {
    await page.setViewportSize({ width, height }); await settle(page); await align(page); await settle(page);
    const b = await bounds(page);
    check(`resize ${width}: no horizontal document overflow`, b.documentWidth <= width, b);
    if (width > 720) {
      check(`resize ${width}: matching pane boundaries`, near(b.picks.bottom, b.detail.bottom), b);
      await visibleSelected(page, 'resize ' + width);
    } else check(`resize ${width}: no stale vertical scrolling on mobile`, b.detail.scrollTop === 0 && b.list.scrollTop === 0 && b.detail.scrollHeight <= b.detail.clientHeight + 2, b);
    metrics.journeys.push({ tag: 'resize-' + width, ...b });
    await shot(page, 'resize-' + width);
  }
  eq('resize: no unexpected browser errors', [...resized.errors], []);
  await resized.context.close();
  await saveMetrics();
}
