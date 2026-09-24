// Real retained publication excerpt + explicitly synthetic precedence controls.
// No scan, provider/model calls, historical rewrite or browser-only regrading.
import { readFile, mkdir } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const FIXTURE = path.join(ROOT, 'tests/fixtures/grading/fallback-risk');
const NOW = '2026-09-23T00:40:00Z';
const riskSel = '#detail [data-item="risk"]';
const warningSel = '#detail .ss-screening-warnings';
const text = async (p, s) => await p.locator(s).count() ? p.locator(s).first().textContent() : '';
const route = async (p, ticker) => { await p.evaluate(t => window.SCStock.navigate('#/explore/bursts/' + t), ticker); await p.waitForTimeout(50); };

export async function checkRiskAttribution({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- risk attribution: retained September 22 and synthetic precedence controls');
  const retained = JSON.parse(gunzipSync(await readFile(path.join(FIXTURE, 'record.json.gz'))));
  const source = JSON.parse(await readFile(path.join(FIXTURE, 'source.json'), 'utf8'));
  const hsic = retained.bursts.find(b => b.ticker === 'HSIC');
  eq('HSIC retained directory basis', source.directory_rows.find(r => r.symbol === 'HSIC').industry, 'Medical Specialities');
  check('KYMR retained industry is biotechnology text', source.directory_rows.find(r => r.symbol === 'KYMR').industry.startsWith('Biotechnology:'));
  eq('HSIC real fallback regression input', [hsic.flags, hsic.claude.source, hsic.claude.key_risk, hsic.plan, hsic.grade, hsic.score], [['biotech'], 'fallback', null, null, 'A+', 9]);

  async function load(record = retained, width = 1440, extra = {}) {
    return open(browser, base, '/risk-attribution-offline.json', NOW, width, {
      lens: 'all', hash: '#/explore/bursts/HSIC', reducedMotion: 'reduce', ...extra,
      beforeLoad: async p => {
        await p.route('**/risk-attribution-offline.json', r => r.fulfill({ json: record }));
        // All evidence stays local. No optional live run-log lookup during this check.
        await p.route('https://api.github.com/**', r => r.abort());
      }
    });
  }
  for (const width of [1440, 390, 320]) for (const theme of ['dark', 'light']) {
    const { page: p, context, errors } = await load(retained, width, { theme, touch: width < 400 });
    try {
      for (const ticker of ['HSIC', 'IOSP', 'KYMR']) {
        await route(p, ticker);
        const row = retained.bursts.find(b => b.ticker === ticker);
        const risk = await text(p, riskSel), warning = await text(p, warningSel);
        check(`${width} ${theme} ${ticker}: unavailable risk is explicit`, risk.includes('Stock-specific risk unavailable') && risk.includes('no accepted reader or plan risk'));
        check(`${ticker}: header never labels the company biotech`, !await p.locator('#detail .sc-chip').evaluateAll(ns => ns.some(n => /^biotech[.]?$/i.test(n.textContent.trim()))));
        if (row.flags.includes('biotech')) {
          check(`${ticker}: broad category warning stays separate`, /healthcare/i.test(warning) && /screening warning/i.test(warning));
          check(`${ticker}: classification and event-risk limits are explicit`, warning.includes('does not establish') && warning.includes('biotechnology company') && warning.includes('event risk'));
          check(`${ticker}: unavailable exact basis is honest`, warning.includes('basis unavailable'));
          check(`${ticker}: raw flag preserved in provenance`, (await text(p, '#disc-provenance [data-recorded-flags]')).includes('biotech'));
        } else eq('IOSP invents no category warning', warning, '');
        check(`${ticker}: final grade and score stay visible`, (await text(p, '#detail .ss-detail__chips')).includes('A+ · ' + row.score.toFixed(1)));
        check(`${ticker}: fallback stays explicit`, (await text(p, '#disc-provenance')).includes('checklist alone; no usable chart-reader judgement'));
        check(`${ticker}: red regime remains the wait reason`, (await text(p, '#detail [data-item="wait"]')).includes('breadth is red'));
        check(`${ticker}: receipt keeps regime gate`, (await text(p, '#disc-provenance')).includes('No ticket: regime gate.'));
        const decision = await p.evaluate(t => { const c = window.SCStock.model.byId['bursts:' + t]; return { plan: c.plan, status: c.status, row: c.row }; }, ticker);
        eq(`${ticker}: no plan or ticket created`, [decision.plan, decision.status], [null, 'no_new_longs']);
        eq(`${ticker}: original row and receipt untouched`, decision.row, row);
        eq(`${ticker}: evidence identity`, decision.row.evidence.id, source.candidate_evidence_ids[ticker]);
      }
      await route(p, 'HSIC');
      for (const [key, verdict] of [['consolidation', 'partial'], ['range_expansion', 'fail'], ['volume', 'fail']]) {
        eq('HSIC recorded ' + key + ' still ' + verdict, await p.locator('#disc-checklist [data-check="' + key + '"]').getAttribute('data-verdict'), verdict);
      }
      const risk = p.locator(riskSel);
      await risk.scrollIntoViewIfNeeded();
      check(`${width}: warning wraps inside viewport`, await p.evaluate(() => {
        const warning = document.querySelector('#detail .ss-screening-warnings');
        return !!warning && warning.scrollWidth <= warning.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth;
      }));
      check('unavailable risk precedes screening warning', await risk.evaluate(n => {
        const warning = n.querySelector('.ss-screening-warnings'), first = n.querySelector('p');
        return !!warning && !!first && !!(first.compareDocumentPosition(warning) & Node.DOCUMENT_POSITION_FOLLOWING);
      }));
      if (shotsDir) {
        await mkdir(shotsDir, { recursive: true });
        await risk.screenshot({ path: path.join(shotsDir, `risk-HSIC-${width}-${theme}.png`) });
        await p.screenshot({ path: path.join(shotsDir, `risk-context-${width}-${theme}.png`) });
      }
      // Existing native provenance disclosure is the only explanatory affordance.
      const summary = p.locator('#disc-provenance > summary');
      await summary.focus(); await p.keyboard.press('Enter');
      check('raw flag disclosure opens by keyboard', await p.locator('#disc-provenance').getAttribute('open') !== null);
      if (width < 400) { await summary.tap(); await summary.tap(); }
      eq('provenance focus stays on its summary', await summary.evaluate(n => document.activeElement === n), true);
      // Same category interpretation on comparison, with risk and warning in separate rows.
      await p.locator('#detail [data-pin]').click(); await route(p, 'KYMR');
      await p.locator('#detail [data-pin]').click(); await p.locator('#compare-open').click();
      const concern = await text(p, '#compare [data-fact="concern"]');
      check('comparison cannot substitute a category for absent risk', concern.includes('Stock-specific risk unavailable') && !concern.includes('Biotech.'));
      check('comparison has the same separate category explanation', (await text(p, '#compare [data-fact="screening"]')).includes('does not establish'));
      check(`${width}: both comparison risk columns fit without clipping`, await p.locator('#compare-table').evaluate(n => {
        const box = n.getBoundingClientRect(), parent = n.closest('dialog').getBoundingClientRect();
        return box.left >= parent.left && box.right <= parent.right && [...n.querySelectorAll('td')].every(c => c.scrollWidth <= c.clientWidth + 1);
      }));
      if (shotsDir) {
        await p.locator('#compare [data-fact="screening"]').scrollIntoViewIfNeeded();
        await p.screenshot({ path: path.join(shotsDir, `risk-compare-${width}-${theme}.png`) });
      }
      await p.locator('#compare-close').click();
      eq('comparison returns focus to opener', await p.evaluate(() => document.activeElement.id), 'compare-open');
      eq('comparison retains selected stock', await p.locator('#detail-h2').textContent(), 'KYMR');
      eq('publication is never rewritten by navigation', await p.evaluate(() => window.SCStock.data), retained);
      eq('risk acceptance browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  const controls = [
    ['accepted reader over plan', b => { b.claude = { source: 'claude', key_risk: 'Accepted reader observation.' }; b.plan = { stop_risk_reason: 'Plan distance concern.' }; }, 'Unverified chart-reader commentary: Accepted reader observation.', 'Plan-derived risk:'],
    ['plan over rejected reader text', b => { b.claude.key_risk = 'Rejected reader text must not become risk.'; b.plan = { stop_risk_reason: 'Plan distance concern.', hazards: ['Other hazard.'] }; }, 'Plan-derived risk: Plan distance concern.', 'Rejected reader text'],
    ['plan hazards', b => { b.plan = { hazards: ['Recorded gap exposure.'] }; }, 'Plan-derived risk: Recorded gap exposure.', 'Stock-specific risk unavailable'],
    ['plan notes', b => { b.plan = { notes: ['Recorded plan limitation.'] }; }, 'Plan-derived risk: Recorded plan limitation.', 'Stock-specific risk unavailable'],
    ['rejected reader without plan', b => { b.claude.key_risk = 'Rejected reader text must not become risk.'; }, 'Stock-specific risk unavailable', 'Rejected reader text'],
    ['no category flags', b => { b.flags = []; }, 'Stock-specific risk unavailable', 'Recorded screening warning'],
    ['legacy unknown basis', b => { delete b.evidence; b.flags = ['biotech', 'foreign']; }, 'Stock-specific risk unavailable', 'Biotech.']
  ];
  for (const [name, mutate, expected, forbidden] of controls) {
    const record = structuredClone(retained), b = record.bursts.find(b => b.ticker === 'HSIC'); mutate(b);
    if (name === 'legacy unknown basis') { delete record.run.evidence; delete record.run.universe; }
    const { page: p, context, errors } = await load(record);
    try {
      const risk = await text(p, riskSel);
      check(name + ': exact risk precedence', risk.includes(expected) && !risk.includes(forbidden));
      if (b.flags.length) check(name + ': category flag is still not a stock assessment', (await text(p, warningSel)).includes('does not establish'));
      if (name === 'legacy unknown basis') check(name + ': no manufactured classification', /basis unavailable/.test(await text(p, warningSel)) && !(await text(p, warningSel)).includes('Medical Specialities'));
      await p.locator('#detail [data-pin]').click(); await route(p, 'IOSP'); await p.locator('#detail [data-pin]').click(); await p.locator('#compare-open').click();
      const concern = await text(p, '#compare [data-fact="concern"] td');
      check(name + ': comparison uses identical precedence', concern.includes(expected) && !concern.includes(forbidden));
      eq(name + ': record untouched', await p.evaluate(() => window.SCStock.data), record);
      eq(name + ': browser errors', [...errors], []);
    } finally { await context.close(); }
  }
}
