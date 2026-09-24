// Full retained Sep 23 publication; all regime/coverage projections below are
// labelled synthetic and discard receipts that belong to the original RED run.
import { readFile, mkdir } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-24T01:00:00Z';
const budget = ['NDSN', 'OPY', 'RRR', 'STE', 'TTE', 'WLY'];
const route = async (p, ticker) => {
  await p.evaluate(t => window.SCStock.navigate('#/explore/bursts/' + t), ticker);
  await p.waitForTimeout(40);
};

export async function checkReaderCoverage({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- reader coverage: retained September 23 and deterministic regime projections');
  const retained = JSON.parse(gunzipSync(await readFile(path.join(ROOT, 'tests/fixtures/grading/reader-coverage/2026-09-23.json.gz'))));
  const original = JSON.stringify(retained);
  const text = (p, s) => p.locator(s).textContent();
  async function load(data, width, theme, now = NOW, ticker = 'NDSN') {
    return open(browser, base, '/reader-coverage-offline.json', now, width, {
      lens: 'all', hash: '#/explore/bursts/' + ticker, theme, touch: width < 400, reducedMotion: 'reduce',
      beforeLoad: async p => {
        await p.route('**/reader-coverage-offline.json', r => r.fulfill({ json: data }));
        await p.route('https://api.github.com/**', r => r.abort());
      }
    });
  }
  for (const width of [1440, 390]) for (const theme of ['dark', 'light']) {
    const { page: p, context, errors } = await load(retained, width, theme);
    try {
      for (const [ticker, state, grade] of [['NDSN', 'unknown', 'A'], ['VEEV', 'fallback', 'A'], ['MET', 'accepted', 'C']]) {
        await route(p, ticker);
        eq(`${width} ${theme} ${ticker}: reader state distinct`, await p.locator('#detail [data-reader-coverage]').getAttribute('data-reader-coverage'), state);
        check(`${ticker}: final grade visible`, (await text(p, '#detail .ss-detail__chips')).includes(grade + ' ·'));
        eq(`${ticker}: raw candidate unchanged`, await p.evaluate(t => window.SCStock.model.byId['bursts:' + t].row, ticker), retained.bursts.find(b => b.ticker === ticker));
        const why = await text(p, '#detail [data-item="why"]');
        if (state !== 'accepted') check(`${ticker}: unknown is not failed setup`, why.includes('not a measured setup failure'));
        else check('MET: accepted downgrade explains both grades', why.includes('Mechanical grade A; reader-reviewed final grade C'));
        eq(`${ticker}: RED creates no copy action`, await p.locator('#detail [data-copy]').count(), 0);
        if (ticker === 'VEEV') check('rejected/unavailable distinguished from confirmation', why.includes('rejected or unavailable'));
        if (ticker === 'NDSN') check('legacy missing reason is not invented as budget', why.includes('reason for missing coverage is not recorded') && !why.includes('call budget'));
      }
      await route(p, 'NDSN');
      await p.locator('#detail [data-pin]').click();
      await route(p, 'VEEV');
      await p.locator('#detail [data-pin]').click();
      await p.locator('#compare-open').click();
      const compared = await text(p, '#compare [data-fact="provenance"]');
      check('comparison preserves missing/fallback distinction', compared.includes('Not reviewed') && compared.includes('Reader fallback'));
      check('comparison preserves unknown judgement', compared.includes('reader judgement unknown'));
      await p.keyboard.press('Escape');
      await p.locator('#disc-provenance > summary').focus();
      await p.keyboard.press('Enter');
      check('coverage disclosure opens by keyboard', await p.locator('#disc-provenance').evaluate(n => n.open));
      check(`${width}: no horizontal overflow`, await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await p.locator('#detail').screenshot({ path: path.join(shotsDir, `coverage-retained-VEEV-${width}-${theme}.png`) });
      }
      eq('retained browser errors', errors, []);
    } finally { await context.close(); }
  }
  for (const verdict of ['green', 'yellow']) for (const width of [1440, 390]) {
    const projected = structuredClone(retained);
    projected.fixture = 'synthetic-reader-coverage-' + verdict;
    projected.run.run_id = null;
    delete projected.run.evidence;
    projected.cover.h1 = 'Synthetic ' + verdict.toUpperCase() + ' coverage check';
    projected.cover.dek = 'Retained candidate states; no rescan or new reader responses.';
    Object.assign(projected.breadth.regime, { verdict, size_multiplier: verdict === 'green' ? 1 : 0.5, reasons: ['Synthetic regime for coverage acceptance.'] });
    for (const b of projected.bursts) {
      b.reader_coverage = b.claude?.source === 'claude' ? 'accepted' : b.claude?.source === 'fallback' ? 'fallback' : 'not_selected_budget';
      delete b.evidence;
    }
    const { page: p, context, errors } = await load(projected, width, 'dark');
    try {
      for (const ticker of [...budget, 'VEEV']) {
        await route(p, ticker);
        const state = await p.evaluate(t => { const c = window.SCStock.model.byId['bursts:' + t]; return [c.grade, c.status, c.plan]; }, ticker);
        eq(`${verdict} ${ticker}: research visible, no plan`, state, ['A', verdict === 'green' ? 'reader_required' : 'not_admitted', null]);
        eq(`${ticker}: no order copy offered`, await p.locator('#detail [data-copy]').count(), 0);
        const label = await text(p, '#detail [data-reader-coverage]');
        eq(`${ticker}: explicit selection label`, label, ticker === 'VEEV' ? 'Reader fallback' : 'Not reviewed · call budget');
        check(`${ticker}: neutral coverage tone`, await p.locator('#detail [data-reader-coverage]').evaluate(n => !n.className.includes('danger') && !n.className.includes('good')));
      }
      await route(p, 'MET');
      eq('accepted C downgrade still ineligible', await p.evaluate(() => window.SCStock.model.byId['bursts:MET'].status), 'below_grade');
      await route(p, 'NDSN');
      check('reader limitation named in decision', (await text(p, '#detail [data-item="why"]')).includes('reader judgement remains unknown'));
      if (verdict === 'yellow') check('YELLOW A+ rule still named', (await text(p, '#detail [data-item="need"]')).includes('yellow night admits A+ only'));
      check('page does not overflow', await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      if (shotsDir) await p.locator('#detail').screenshot({ path: path.join(shotsDir, `coverage-${verdict}-NDSN-${width}.png`) });
      eq('projection browser errors', errors, []);
    } finally { await context.close(); }
  }
  // Accepted reader A+ controls use actual offline-pipeline fixtures and plans.
  for (const variant of ['full', 'yellow']) {
    const data = JSON.parse(await readFile(path.join(ROOT, `tests/fixtures/page/${variant}.json`), 'utf8'));
    const ticker = data.trades[0];
    const { page: p, context, errors } = await load(data, 390, 'light', '2026-09-10T22:31:00Z', ticker);
    try {
      eq('accepted control remains a ticket', await p.evaluate(t => window.SCStock.model.byId['bursts:' + t].status, ticker), 'ticket');
      check('accepted control retains copy action', await p.locator('#detail [data-copy]').count() > 0);
      eq('accepted coverage label', await text(p, '#detail [data-reader-coverage]'), 'Reader reviewed');
      eq('accepted control browser errors', errors, []);
    } finally { await context.close(); }
  }
  eq('retained source was never rewritten by projections', JSON.stringify(retained), original);
}
