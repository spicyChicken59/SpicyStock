// Read the real producer's review allocation; renderer-only corruptions never
// become publication fixtures or ticket authority.
import { readFile, mkdir } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const NOW = '2026-09-10T22:31:00Z';
// report.H1_READER_WAIT: the one headline whose claim the cover's selection line answers
const READER_WAIT = 'No new burst tickets. Reader review incomplete.';

async function checkMethodSelection({ browser, base, open, check, eq, shotsDir }) {
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

// These are immutable producer records, including the exact retained October9
// publication. Corruptions below are renderer-only inputs, never new fixtures
// or source evidence. The seeded/dirty private facts are explicitly synthetic.
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const HANDOFF_KEY = 'spicystock:handoff:v1';
async function controls() {
  const stem = path.join(ROOT, 'tests/fixtures/stop-research/current');
  const [canonical, reader, legacyRaw] = await Promise.all([
    readFile(stem + '-publication.json.gz').then(gunzipSync), readFile(stem + '-reader.json.gz').then(gunzipSync),
    readFile(path.join(ROOT, 'tools/handoff_model_cases.mjs'), 'utf8')
  ]);
  const match = legacyRaw.match(/^const LEGACY_V2_RAW = ("(?:[^"\\]|\\.)*");$/m);
  if (!match) throw Error('Original module-produced synthetic private v2 control missing');
  const result = [{ name: 'retained-current', raw: canonical, reader, now: '2026-10-10T12:01:00Z', data: JSON.parse(canonical), seed: JSON.parse(match[1]) }];
  for (const name of ['full', 'notrade', 'degraded', 'red', 'empty', 'partial']) {
    const raw = await readFile(path.join(ROOT, 'tests/fixtures/page', name + '.json'));
    result.push({ name, raw, data: JSON.parse(raw), now: NOW });
  }
  const raw = gunzipSync(await readFile(path.join(ROOT, 'tests/fixtures/grading/reader-coverage/2026-09-23.json.gz')));
  result.push({ name: 'genuine-legacy', raw, data: JSON.parse(raw), now: '2026-09-24T01:00:00Z' });
  return result;
}

// Renderer-only copies of full.json, not publications or source evidence.
// Expected counters/verdicts were independently derived with unchanged
// review_selection.receipt + reader_coverage.reads and grader._error_text.
// In particular the actual src.* class prefixes differ from bare/wrapped text.
function rendererReadControls(full) {
  const cases = [
    ['partial transport', 'RuntimeError: unavailable', 'transport'],
    ['partial authority', 'src.ReaderAuthorityError: scope', 'refused'],
    ['partial discovery', 'src.DiscoveryConflict: scope', 'refused'],
    ['partial format', 'src.ScoreFormatError: bad score', 'format'],
    ['partial account', 'AuthenticationError: refused', 'account'],
    ['partial credit', 'BadRequestError: credit balance is too low', 'credit'],
    ['bare authority is transport', 'ReaderAuthorityError: scope', 'transport'],
    ['bare format is transport', 'ScoreFormatError: score', 'transport'],
    ['wrapped authority is transport', 'wrapped src.ReaderAuthorityError: scope', 'transport'],
    ['all unavailable', 'RuntimeError: unavailable', 'transport', true],
    ['tolerated research refusal', 'src.ReaderAuthorityError: scope', 'refused', false, true]
  ];
  return cases.map(([name, error, cause, all = false, veto = false]) => {
    const data = structuredClone(full), s = data.run.review_selection, reads = data.run.reads;
    if (s.requested !== 4 || s.selected.at(-1).ticker !== 'TSLA' || s.by_purpose.opportunity.requested !== 3 || s.by_purpose.research_ranked.requested !== 1) throw Error('Genuine full producer control changed; rederive reader oracle');
    const target = data.bursts.find(row => row.ticker === 'TSLA');
    for (const row of all ? data.bursts.filter(row => row.review_selection.selected) : [target]) {
      row.claude = { source: 'fallback', error, attempts: [{}] }; row.grade = row.grade_mechanical; row.reader_coverage = 'fallback';
    }
    if (veto) {
      target.vetoes = ['thin']; target.review_selection.blockers.unshift('quality_veto');
      target.evidence.review_selection = structuredClone(target.review_selection); s.blockers.quality_veto += 1;
    }
    Object.assign(s.by_purpose.opportunity, { accepted: all ? 0 : 3, unaccepted: all ? 3 : 0, refused: 0, attempts: 3 });
    Object.assign(s.by_purpose.research_ranked, { accepted: 0, unaccepted: 1, refused: cause === 'refused' ? 1 : 0, attempts: 1 });
    s.attempts = 4;
    reads.done = all ? 0 : 3;
    reads.causes = { refused: 0, format: 0, account: 0, credit: 0, transport: 0 }; reads.causes[cause] = all ? 4 : 1;
    reads.refused_names = cause === 'refused' ? ['TSLA'] : []; reads.refused_admissible = cause === 'refused' && !veto ? ['TSLA'] : [];
    reads.verdict = all ? 'unavailable' : veto ? 'tolerated' : 'partial';
    reads.unavailable_reason = veto ? 'refused within the tolerance' : 'see problems';
    return { name, data, cause, done: reads.done, expected: reads.verdict };
  });
}

export async function checkReviewSelection(args) {
  await checkMethodSelection(args);
  const { browser, base, open, check, eq, shotsDir } = args;
  console.log('-- review selection clarity: selected batch vs coverage, original verdict and private continuity');
  const fixtures = await controls();
  const text = async (page, selector) => await page.locator(selector).count() ? page.locator(selector).first().textContent() : '';
  const run = async (name, fn) => { try { await fn(); } catch (error) { check(name + ': workflow completes', false, error.stack); } };
  const state = page => page.evaluate(() => ({
    record: JSON.stringify(SCStock.data), plans: JSON.stringify(Object.values(SCStock.model.stages).flat().map(row => [row.id, row.status, row.plan])),
    trades: JSON.stringify(SCStock.data.trades), privateRaw: localStorage.getItem('spicystock:handoff:v1'),
    following: localStorage.getItem('spicystock:following:v1'), cash: document.getElementById('morning-cash').value,
    binding: SCStock.observations.facts().recordHash
  }));
  const capture = async (page, name, selector) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true });
    await page.locator(selector).scrollIntoViewIfNeeded();
    await page.locator(selector).screenshot({ path: path.join(shotsDir, name + '.png') });
  };
  const launch = async (fixture, width = 1280) => {
    const requests = [];
    // The controlled Date is the real ticking clock. Passing SCStock.now would
    // deliberately pin the app and make reclock/cutoff controls ineffective.
    const tab = await open(browser, base, fixture.reader ? null : '/review-selection-offline.json', null, width, {
      theme: width === 390 ? 'light' : 'dark', lens: 'all', reducedMotion: 'reduce', beforeLoad: async (page, context) => {
        page.setDefaultTimeout(5000);
        await context.addInitScript(({ now, seed, key }) => {
          const NativeDate = Date; window.__reviewClock = Date.parse(now);
          window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [window.__reviewClock])); } static now() { return window.__reviewClock; } };
          if (seed) localStorage.setItem(key, seed);
          const put = Storage.prototype.setItem, drop = Storage.prototype.removeItem;
          window.__reviewWrites = 0;
          Storage.prototype.setItem = function (name, raw) { if (name === key) window.__reviewWrites++; return put.call(this, name, raw); };
          Storage.prototype.removeItem = function (name) { if (name === key) window.__reviewWrites++; return drop.call(this, name); };
          window.__reviewCopies = 0;
          Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { window.__reviewCopies++; } } });
        }, { now: fixture.now, seed: fixture.seed || null, key: HANDOFF_KEY });
        context.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
        await context.route('**/*', async route => {
          const url = new URL(route.request().url());
          if (url.origin !== base) { await route.fulfill({ contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'application/json', body: url.hostname === 'fonts.googleapis.com' ? '' : '{}' }); return; }
          if (url.pathname === '/review-selection-offline.json') { await route.fulfill({ contentType: 'application/json', body: fixture.raw }); return; }
          if (fixture.reader && url.pathname === '/docs/reader.json') { await route.fulfill({ contentType: 'application/json', body: fixture.reader }); return; }
          if (url.pathname === '/docs/morning.json') { await route.fulfill({ contentType: 'application/json', body: '{}' }); return; }
          await route.continue();
        });
      }
    });
    if (fixture.reader) await tab.page.waitForFunction(() => SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    return { ...tab, requests };
  };

  for (const fixture of fixtures) for (const width of fixture.name === 'retained-current' ? [390, 1280] : [1280]) {
    await run(fixture.name + '/' + width, async () => {
      const tab = await launch(fixture, width), { page } = tab, name = fixture.name + '/' + width;
      try {
        const present = await page.evaluate(() => typeof SCStock.reviewSelectionFacts === 'function');
        check(name + ': shared reconciled selection API is present', present);
        if (!present) return;
        const before = await state(page), start = tab.requests.length;
        const facts = await page.evaluate(() => SCStock.reviewSelectionFacts(SCStock.data));
        if (fixture.name === 'genuine-legacy') {
          eq('legacy: unknown selection cannot acquire reconciled facts', facts, null);
          eq('legacy: original primary verdict remains unchanged', await text(page, '#cover-h1'), fixture.data.cover.h1);
          eq('legacy: a headline with no review claim keeps the cover to its own sentences', await page.locator('#cover-review-box').isVisible(), false);
          check('legacy: selection limitation is explicit in the morning desk', /unknown|unavailable|not recorded|not established|not reconciled/i.test(await text(page, '[data-morning="review-selection"]')));
        } else {
          check(name + ': genuine producer reconciles rich selection and batch facts', !!facts?.detail);
          if (!facts?.detail) return;
          const s = fixture.data.run.review_selection, reads = fixture.data.run.reads, detail = facts.detail;
          eq(name + ': opportunity and research counts reflect recorded selection', [detail.feasible, detail.opportunity, detail.research, detail.unselected], [s.feasible, s.by_purpose.opportunity.requested, s.by_purpose.research_ranked.requested + s.by_purpose.research_rotating.requested, s.discovered - s.requested]);
          eq(name + ': accepted/unaccepted/refused and verdict reconcile actual batch', [detail.requested, detail.accepted, detail.unaccepted, detail.refused, detail.verdict], [reads.requested, reads.done, reads.requested - reads.done, reads.causes.refused, reads.verdict]);
          eq(name + ': cover holds the shared measured selection summary', await text(page, '[data-review-selection="cover"]'), detail.summary);
          const waits = fixture.data.cover.h1 === READER_WAIT;
          eq(name + ': the cover shows the selection line only under the reader-wait headline', await page.locator('#cover-review-summary').isVisible(), waits);
          if (waits) check(name + ': the collapsed line answers the headline with the batch and the unreviewed A-band', (await text(page, '#cover-review-summary')) ===
            'Chart reviews: ' + (detail.requested ? detail.accepted + ' of ' + detail.requested + ' selected accepted' : 'none selected') + ' · ' + detail.unreviewedQuality + ' mechanical A+/A not reviewed', await text(page, '#cover-review-summary'));
          check(name + ': final review/cash gates are never called cleared', /Final review and combined cash allocation still decide tickets/.test(facts.note));
          if (fixture.name === 'retained-current') {
            eq('actual retained f5: original canonical and reader bytes stay bound', await page.evaluate(() => { const f = SCStock.observations.facts(); return [f.canonicalHash, f.recordHash, f.projected]; }), [sha(fixture.raw), sha(fixture.reader), true]);
            eq('actual retained f5: known zero fit and completed research sample remain exact', [detail.feasible, detail.opportunity, detail.research, detail.requested, detail.accepted, detail.unreviewedQuality], [0, 0, 2, 2, 2, 51]);
            check('actual retained f5: primary verdict no longer calls selected work incomplete', !/Reader review incomplete/i.test(await text(page, '#cover-h1')));
            check('actual retained f5: remaining reader coverage is explicitly limited', /coverage|unreviewed|not reviewed/i.test(detail.coverage) && !/complete (universe|news|coverage)|all (stocks|candidates).*reviewed/i.test(detail.coverage));
            check('actual retained f5: readable summary distinguishes all unselected names and A-band coverage', /477 of 479 reaction candidates not selected; 51 mechanical A\+\/A lack accepted review/.test(detail.summary));
            check('actual retained f5: original published verdict remains dated and unchanged', (await text(page, '#cover-published')).includes(fixture.data.cover.h1) && /2026-10-09|Oct 9/.test(await text(page, '#cover-published-label')));
            eq('actual retained f5: the line reads the retained batch and A-band', await text(page, '#cover-review-summary'), 'Chart reviews: 2 of 2 selected accepted · 51 mechanical A+/A not reviewed');
            eq('actual retained f5: the summary and the dated original are collapsed until asked for', await page.locator('#cover-review').isVisible(), false);
            await capture(page, 'review-current-cover-' + width, '#market-bar');
            await page.locator('#cover-review-summary').focus(); await page.keyboard.press('Enter');
            eq('actual retained f5: the keyboard opens the summary and the dated original', [await page.locator('#cover-review').isVisible(), await page.locator('#cover-published').isVisible()], [true, true]);
            await capture(page, 'review-current-cover-open-' + width, '#market-bar');
            await page.locator('#cover-review-summary').click();
          }
          if (fixture.name === 'red') eq('RED: completed research never rewrites stand-aside primary verdict', await text(page, '#cover-h1'), fixture.data.cover.h1);
          if (fixture.name === 'full') eq('feasible: completed selected work preserves the published trade verdict', await text(page, '#cover-h1'), fixture.data.cover.h1);
          if (fixture.name === 'notrade') check('downgrade: completed work is separate from no final tickets', detail.accepted === 4 && detail.feasible === 3 && fixture.data.trades.length === 0 && !/no candidates? (fit|passed)/i.test(detail.selection));
          if (fixture.name === 'degraded') check('unavailable: failed selected work remains incomplete rather than zero feasible', detail.feasible === 3 && detail.accepted === 0 && /incomplete|unavailable|unaccepted|not accepted/i.test(detail.batch));
          if (fixture.name === 'empty' || fixture.name === 'partial') check(name + ': zero requests are never called accepted completed work', detail.requested === 0 && detail.accepted === 0 && /no.*(request|review)|not asked|0.*requested/i.test(detail.batch));
          if (fixture.name === 'partial') check('partial input: empty selected work does not erase incomplete input coverage', /incomplete|subset/i.test(await text(page, '#cover-dek') + await text(page, '#cover-coverage')));
        }
        await page.locator('#morning-open').focus(); await page.keyboard.press('Enter');
        eq(name + ': keyboard opens the existing morning dialog', await page.locator('#morning-desk').evaluate(node => node.open), true);
        const rich = facts?.detail;
        if (rich) eq(name + ': morning and cover use the same selection facts', await text(page, '[data-morning="review-selection"]'), rich.summary);
        if (fixture.name === 'retained-current') {
          check('actual retained f5: morning primary reason distinguishes complete research from zero opportunity fit', !/Reader review incomplete/i.test(await text(page, '[data-morning="reason"]')) && /review|research|feasible|fit/i.test(await text(page, '[data-morning="reason"]')));
          check('actual retained f5: morning retains the dated original headline', (await text(page, '[data-morning="published-verdict"]')).includes(fixture.data.cover.h1));
          await capture(page, 'review-current-morning-' + width, '#morning-desk');
          if (!await page.locator('.ss-morning__prep').evaluate(node => node.open)) await page.locator('.ss-morning__prep > summary').click();
          await page.locator('#morning-cash').fill('125.');
          await page.locator('#morning-handoffs > summary').click();
          if (!await page.locator('[data-handoff-report]').evaluate(node => node.open)) await page.locator('[data-handoff-report] > summary').click();
          const input = page.locator('[data-handoff-field="average_price"]'); await input.fill('111.25'); await input.focus();
          await page.evaluate(() => { window.__reviewPrivateNode = document.querySelector('[data-handoff-field="average_price"]'); window.__reviewCashNode = document.getElementById('morning-cash'); });
          await page.evaluate(() => { window.__reviewClock += 60000; SCStock.reclock(); });
          eq('selection explanation: real unpinned clock advances', await page.evaluate(() => SCStock.avail.at.toISOString()), '2026-10-10T12:02:00.000Z');
          eq('selection explanation: clock update preserves private node/value/focus', await input.evaluate(node => [node === window.__reviewPrivateNode, node.value, document.activeElement === node]), [true, '111.25', true]);
          eq('selection explanation: cash draft retains exact node and partial decimal', await page.locator('#morning-cash').evaluate(node => [node === window.__reviewCashNode, node.value]), [true, '125.']);
          eq('selection explanation: no private save or migration occurs', await page.evaluate(() => [window.__reviewWrites, localStorage.getItem('spicystock:handoff:v1')]), [0, fixture.seed]);
          await page.locator('[data-morning="next"]').focus(); await page.keyboard.press('Enter');
          await page.waitForFunction(() => !document.getElementById('morning-desk').open && document.querySelector('#decision-gates details')?.open && document.activeElement.matches('[data-wait-summary]'));
          check('selection explanation: keyboard research action returns to existing gates with focus', await page.locator('#view-explore').isVisible());
          eq('anticipation: burst selection never replaces its separate five baseline decisions', await page.locator('[data-anticipation-refusal]').count(), 5);
          for (const ticker of ['MG', 'KE', 'ZIM', 'SN', 'PSNL']) check('anticipation ' + ticker + ': original recorded refusal remains visible', !!(await text(page, '[data-anticipation-refusal="' + ticker + '"]')));
          await capture(page, 'review-current-gates-' + width, '#decision-gates');
          await page.locator('#morning-open').click();
          eq('selection explanation: inspection navigation preserves exact dirty input and cash nodes', await page.evaluate(() => [document.querySelector('[data-handoff-field="average_price"]') === window.__reviewPrivateNode, window.__reviewPrivateNode.value, document.getElementById('morning-cash') === window.__reviewCashNode, window.__reviewCashNode.value]), [true, '111.25', true, '125.']);
          for (const [phase, now] of [['ended', '2026-10-12T14:00:00Z'], ['stale', '2026-10-14T13:40:00Z']]) {
            await input.focus();
            eq(phase + ': real clock transition repaints current availability', await page.evaluate(now => { window.__reviewClock = Date.parse(now); return SCStock.reclock(); }, now), true);
            check(phase + ': availability actually crosses the tested boundary', await page.evaluate(phase => phase === 'ended' ? SCStock.avail.phase === 'ended' : SCStock.avail.pubBlocked, phase));
            eq(phase + ': archived-original eyebrow accompanies the exact original H1', await text(page, '#cover-h1'), fixture.data.cover.h1);
            check(phase + ': source selection facts remain separate dated context', (await text(page, '#cover-published-label')).includes('2026-10-09') && (await text(page, '[data-morning="review-selection"]')).includes('2 of 2'));
            eq(phase + ': private report node/value/focus facts are retained', await input.evaluate(node => [node === window.__reviewPrivateNode, node.value, document.activeElement === node]), [true, '111.25', true]);
          }
          await page.evaluate(now => { window.__reviewClock = Date.parse(now); SCStock.reclock(); }, fixture.now);
        }
        const after = await state(page);
        eq(name + ': clarification changes no candidate/order/record/storage/binding authority', { ...after, cash: before.cash }, before);
        eq(name + ': no clipboard or private-store write', await page.evaluate(() => [window.__reviewCopies, window.__reviewWrites]), [0, 0]);
        eq(name + ': inspecting the explanation makes no provider/private request', tab.requests.slice(start), []);
        check(name + ': cover and morning fit phone/desktop', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1 && document.getElementById('morning-desk').scrollWidth <= document.getElementById('morning-desk').clientWidth + 1));
        eq(name + ': no browser error', Array.from(tab.errors), []);
      } finally { await tab.context.close(); }
    });
  }

  await run('renderer-only reconciliation faults', async () => {
    const original = fixtures[0], tab = await launch(original), { page } = tab;
    try {
      const faults = [
        ['accepted total mismatch', d => { d.run.review_selection.by_purpose.research_ranked.accepted = 0; d.run.review_selection.by_purpose.research_ranked.unaccepted = 1; }],
        ['unknown batch verdict', d => { d.run.reads.verdict = 'unknown'; }],
        ['refusal cause mismatch', d => { d.run.reads.causes.refused = 1; }],
        ['unselected feasible mismatch', d => { d.run.review_selection.feasible_unselected = 1; }],
        ['row selection mismatch', d => { d.bursts.find(row => row.review_selection.selected).review_selection.selected = false; }],
        ['row reader evidence mismatch', d => { d.bursts.find(row => row.review_selection.selected).reader_coverage = 'not_selected_budget'; }],
        ['row blocker unknown', d => { d.bursts[0].review_selection.blockers = ['unknown_blocker']; }],
        ['unknown feasibility semantics', d => { d.rules.review_selection.feasibility = 'cleared for execution'; }],
        ['unknown rotation semantics', d => { d.rules.review_selection.rotation = 'latest news'; }],
        ['embedded evidence decision mismatch', d => { d.bursts[0].evidence.review_selection.feasible = true; }],
        ['research pool contradicts archived grade band', d => { d.rules.pipeline.trade_grades = ['B']; }],
        ['unknown policy', d => { d.run.review_selection.policy = d.rules.review_selection.policy = 'unknown'; }],
        ['legacy missing selection', d => { delete d.run.review_selection; delete d.rules.review_selection; }]
      ];
      for (const [name, change] of faults) {
        const data = structuredClone(original.data); change(data);
        const result = await page.evaluate(data => { SCStock.render(data, new Date('2026-10-10T12:01:00Z')); return SCStock.reviewSelectionFacts(data); }, data);
        eq('renderer-only ' + name + ': unsupported reconciliation cannot claim completed batch', result?.detail || null, null);
        eq('renderer-only ' + name + ': original primary verdict stays intact', await text(page, '#cover-h1'), original.data.cover.h1);
        check('renderer-only ' + name + ': limitation is visible in cover', await page.locator('#cover-review-summary').isVisible() && /unknown|unavailable|not recorded|not established|not reconciled/i.test(await text(page, '#cover-review-summary')) &&
          /unknown|unavailable|not recorded|not established|not reconciled/i.test(await text(page, '[data-review-selection="cover"]')));
        eq('renderer-only ' + name + ': no tickets or private writes appear', await page.evaluate(() => [SCStock.data.trades.length, Object.values(SCStock.model.stages).flat().filter(row => row.status === 'ticket').length, window.__reviewWrites]), [0, 0, 0]);
      }
      eq('renderer-only: corruptions never alter exact source fixture bytes', sha(original.raw), 'f5cbe38eaa38647364f4994bb867bbb7da4354e6a8f7f28315fb96e9b650ef0d');
      eq('renderer-only: no browser error', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });

  await run('renderer-only source-helper reader outcomes', async () => {
    const full = fixtures.find(fixture => fixture.name === 'full'), tab = await launch(full), { page } = tab;
    try {
      await page.locator('#morning-open').click();
      for (const control of rendererReadControls(full.data)) {
        const { data, name } = control;
        const result = await page.evaluate(({ data, now }) => { SCStock.render(data, new Date(now)); return SCStock.reviewSelectionFacts(data); }, { data, now: full.now });
        check('renderer-only ' + name + ': exact helper-emitted cause and verdict reconcile', !!result?.detail);
        if (!result?.detail) continue;
        eq('renderer-only ' + name + ': retained counter/verdict oracle', [result.detail.requested, result.detail.accepted, result.detail.unaccepted, result.detail.refused, result.detail.verdict], [4, control.done, 4 - control.done, control.cause === 'refused' ? 1 : 0, control.expected]);
        check('renderer-only ' + name + ': missing selected review is explicit', result.detail.batch.includes('without an accepted review') && (control.expected !== 'tolerated' || result.detail.batch.includes('those names still lack accepted review')));
        eq('renderer-only ' + name + ': original primary verdict is not rewritten', await text(page, '#cover-h1'), full.data.cover.h1);
        eq('renderer-only ' + name + ': cover and morning present the same helper facts', [await text(page, '[data-review-selection="cover"]'), await text(page, '[data-morning="review-selection"]')], [result.detail.summary, result.detail.summary]);
        eq('renderer-only ' + name + ': display adds no raw ticket or private write', await page.evaluate(() => [SCStock.data.trades.length, window.__reviewWrites, window.__reviewCopies]), [full.data.trades.length, 0, 0]);
      }
      eq('renderer-only helper controls: no browser errors', Array.from(tab.errors), []);
    } finally { await tab.context.close(); }
  });
}
