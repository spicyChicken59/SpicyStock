/* The same clocks, after the change: the acceptance criterion is that the
   pinned 11:00 AM test no longer tells the reader to act before 9:28 AM. */
import pw from '/opt/node22/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const page_url = 'file://' + path.join(root, 'docs/index.html');
const RECORDS = { published: 'docs/data.json', 'next (a ticket, for Mon 14 Sep)': 'tests/fixtures/page/next.json' };
const AT = [
  ['Sun 13 Sep  6:00 PM ET (the evening before)', '2026-09-13T22:00:00Z'],
  ['Mon 14 Sep  9:00 AM ET (before the open)',    '2026-09-14T13:00:00Z'],
  ['Mon 14 Sep  9:40 AM ET (inside the window)',  '2026-09-14T13:40:00Z'],
  ['Mon 14 Sep 10:00 AM ET (at the cutoff)',      '2026-09-14T14:00:00Z'],
  ['Mon 14 Sep 11:00 AM ET (the acceptance)',     '2026-09-14T15:00:00Z'],
];
const browser = await chromium.launch();
const out = [];
for (const [label, rel] of Object.entries(RECORDS)) {
  const data = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const t = data.run.timing;
  out.push('', '='.repeat(76), `${label}: measured ${data.run.session}, ${(data.trades||[]).length} trade(s)`,
    `  run.timing: ${t ? t.applicable_session + ' · ' + t.opens_at + ' → ' + t.cutoff_at + ' · ' + t.basis : '(absent)'}`, '='.repeat(76));
  for (const [when, at] of AT) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const pg = await ctx.newPage();
    await pg.goto(page_url + '#/explore/bursts');
    await pg.waitForFunction(() => window.SCStock && window.SCStock.render);
    const said = await pg.evaluate(([d, at]) => {
      window.SCStock.render(d, new Date(at));
      const T = (id) => { const e = document.getElementById(id); return e ? e.textContent.trim() : '(none)'; };
      const a = window.SCStock.avail;
      const order = (d.trades || []).find((x) => { const b = (d.bursts||[]).find((y) => y.ticker === x); return b && b.plan && b.plan.order_json; }) || null;
      let bar = '(no trade)', copies = 0;
      if (order) {
        window.SCStock.navigate('#/explore/bursts/' + order);
        const box = document.querySelector('.ss-action');
        bar = box ? box.innerText.replace(/\s*\n\s*/g, ' / ').trim() : '(no bar)';
        const dp = document.getElementById('disc-plan'); if (dp) dp.open = true;
        copies = document.querySelectorAll('#disc-plan [data-copy]').length;
      }
      return { phase: a.phase, offered: a.offered, pub: a.pub.state, lead: a.lead,
        next: T('next-h3'), next_p: T('next-p'), summary: T('orders-summary'),
        sheet: (document.querySelector('#order-sheet tbody') || {}).innerText || '',
        bar, copies, order,
        recorded: document.querySelectorAll('[data-recorded-ticket]').length };
    }, [data, at]);
    out.push('', `--- ${when}`,
      `  publication ${said.pub} · window ${said.phase} · offered ${said.offered}${said.lead ? ' (' + said.lead + ')' : ''}`,
      `  NEXT  : ${said.next}`,
      `          ${said.next_p}`,
      `  sheet : ${said.summary} | rows: ${said.sheet.split('\n')[0] || '(empty)'}`,
      said.order ? `  ${said.order} bar: ${said.bar}` : '  bar   : (no trade)',
      said.order ? `  copy controls in the plan: ${said.copies} · recorded-ticket blocks: ${said.recorded}` : null);
    await ctx.close();
  }
}
await browser.close();
console.log(out.filter((x) => x !== null).join('\n'));
