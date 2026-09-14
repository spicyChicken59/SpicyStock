/* Session-aware desk — reproduction at pinned clocks, before anything is edited.
   Each record is clocked around the session ITS OWN plans are for (day 1 of the
   plan's dated schedule, which the run wrote), so the ticket path is reachable
   rather than hidden behind a stale chip. */
import pw from '/opt/node22/lib/node_modules/playwright/index.js';
const { chromium } = pw;
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const page_url = 'file://' + path.join(root, 'docs/index.html');
const RECORDS = {
  published: 'docs/data.json',
  'full (a ticket)': 'tests/fixtures/page/full.json',
};

// ET offsets: September is EDT, UTC-4, so 09:00 ET = 13:00Z. Stated, not assumed
// silently: this is the reproduction's own arithmetic, not the page's.
const AT = [
  ['the evening before,  6:00 PM ET', -1, 22],
  ['the session,         9:00 AM ET',  0, 13],
  ['the session,         9:40 AM ET',  0, '13:40'],
  ['the session,        11:00 AM ET',  0, 15],
  ['the session,         3:00 PM ET',  0, 19],
];
const iso = (day, h) => day + 'T' + (typeof h === 'string' ? h : String(h).padStart(2, '0') + ':00') + ':00Z';
const shift = (d, n) => { const x = new Date(d + 'T12:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };

const browser = await chromium.launch();
const out = [];
for (const [label, rel] of Object.entries(RECORDS)) {
  const data = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const order = (data.trades || [])[0] || null;
  const burst = (data.bursts || []).find((b) => b.ticker === order);
  const sched = ((burst || {}).plan || {}).exit_schedule || [];
  const day1 = (sched.find((x) => x && x.key === 'entry') || {}).date || null;
  out.push('', '='.repeat(76),
    `${label}: measured ${data.run.session}, regime ${((data.breadth || {}).regime || {}).verdict}, ` +
    `${(data.trades || []).length} trade(s)`,
    `  run.timing      : ${data.run.timing === undefined ? '(absent)' : JSON.stringify(data.run.timing)}`,
    `  plans are for   : ${day1 || '(no dated schedule — no ticket tonight)'}`,
    '='.repeat(76));
  const base = day1 || shift(data.run.session, 1);
  for (const [when, dayOff, hour] of AT) {
    const at = iso(shift(base, dayOff), hour);
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const pg = await ctx.newPage();
    await pg.goto(page_url + '#/explore/bursts');
    await pg.waitForFunction(() => window.SCStock && window.SCStock.render);
    const said = await pg.evaluate(([d, at, order]) => {
      window.SCStock.render(d, new Date(at));
      const t = (id) => { const e = document.getElementById(id); return e ? e.textContent.trim() : '(none)'; };
      const st = window.SCStock.status(d, new Date(at));
      let action = '(no trade tonight)', ticket = '(none)';
      if (order) {
        window.SCStock.navigate('#/explore/bursts/' + order);
        const a = document.querySelector('.sc-actionbar');
        action = a ? a.innerText.replace(/\s*\n\s*/g, ' / ').trim() : '(no action bar)';
        const dt = document.getElementById('disc-plan');
        if (dt) { dt.open = true; const rows = [...dt.querySelectorAll('dt')].map((x) => x.textContent.trim()); ticket = rows.join(', '); }
      }
      return { state: st.state, chip: st.chip,
        blocked: ['stale1', 'stale2', 'pending', 'failed'].indexOf(st.state) >= 0,
        session_bit: t('bar-facts').replace(/\s*\n\s*/g, ' '),
        next: t('next-h3'), next_p: t('next-p'), action, ticket };
    }, [data, at, order]);
    out.push('', `--- ${when}   (${at})`,
      `  publication : ${said.state}, chip "${said.chip}", blocked ${said.blocked}`,
      `  session bit : ${said.session_bit}`,
      `  NEXT ACTION : ${said.next}`,
      `                ${said.next_p}`,
      order ? `  ${order} action  : ${said.action}` : '  action bar  : (no trade tonight)');
    await ctx.close();
  }
}
await browser.close();
console.log(out.join('\n'));
