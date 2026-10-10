// Read the real producer's review allocation; renderer-only corruptions never
// become publication fixtures or ticket authority.
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-10T22:31:00Z';

export async function checkReviewSelection({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- review selection: opportunity fit, bounded research and legacy absence');
  for (const [variant, feasible, opportunity, research] of [['full', 3, 3, 1], ['red', 0, 0, 2], ['thin', 0, 0, 2]]) {
    const data = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page', variant + '.json'), 'utf8'));
    eq(variant + ': genuine producer has expected review fit', data.run.review_selection.feasible, feasible);
    for (const width of [1280, 390]) {
      const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/' + variant + '.json', NOW, width);
      await page.evaluate(() => SCStock.navigate('#/method'));
      const note = page.locator('#run-meta li').filter({ hasText: 'Before chart review,' });
      eq(variant + '/' + width + ': one review selection explanation', await note.count(), 1);
      const text = await note.textContent();
      check(variant + ': individual fit precedes chart review', text.includes(feasible + ' candidate') && text.includes('current regime and individual model sizing'), text);
      check(variant + ': opportunity and research counts separate', text.includes(opportunity + ' opportunity / ' + research + ' research reviews selected'), text);
      check(variant + ': unused feasible count and final guards explicit', text.includes('0 feasible candidates left unreviewed') && text.includes('Final review and combined cash allocation still decide tickets'), text);
      check(variant + '/' + width + ': explanation does not overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await note.screenshot({ path: path.join(shotsDir, 'review-selection-' + variant + '-' + width + '.png') }); }
      if (variant === 'full' && width === 1280) {
        for (const change of ['legacy', 'unknown_version', 'unknown_policy', 'bad_arithmetic', 'bad_purpose', 'duplicate_selection', 'missing_group']) {
          const changed = structuredClone(data), s = changed.run.review_selection;
          if (change === 'legacy') { delete changed.run.review_selection; delete changed.rules.review_selection; }
          if (change === 'unknown_version') { s.version = 99; changed.rules.review_selection.version = 99; }
          if (change === 'unknown_policy') { s.policy = 'unknown'; changed.rules.review_selection.policy = 'unknown'; }
          if (change === 'bad_arithmetic') s.feasible_unselected += 1;
          if (change === 'bad_purpose') s.selected[0].purpose = 'research_rotating';
          if (change === 'duplicate_selection') s.selected[1].ticker = s.selected[0].ticker;
          if (change === 'missing_group') delete s.by_purpose.opportunity;
          await page.evaluate(({ changed, now }) => SCStock.render(changed, new Date(now)), { changed, now: NOW });
          eq(change + ': no invented selection explanation', await note.count(), 0);
        }
        const archived = structuredClone(data);
        archived.run.review_selection.max_reads = archived.rules.pipeline.max_reads = 9;
        archived.run.review_selection.unused_capacity = 9 - archived.run.review_selection.requested;
        await page.evaluate(({ archived, now }) => SCStock.render(archived, new Date(now)), { archived, now: NOW });
        check('archived capacity is shown instead of current twelve', (await note.textContent()).includes('4 of 9 available reads'));
      }
      eq(variant + '/' + width + ': no page errors', errors, []);
      await context.close();
    }
  }
}
