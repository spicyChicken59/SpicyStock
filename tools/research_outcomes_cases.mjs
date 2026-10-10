/* Frozen research observations: producer fixtures, public transport, no private execution claims. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DIR = path.join(ROOT, 'tests/fixtures/research-outcomes');
const PRIVATE = 'ZZPRIVATE-research-outcomes-234.56';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const canonical = x => Array.isArray(x) ? x.map(canonical) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map(k => [k, canonical(x[k])])) : x;
const json = value => Buffer.from(JSON.stringify(canonical(value)));
const journalRequests = requests => requests.filter(request => /\/research-outcomes(?:\.json|\/)/.test(new URL(request.url).pathname));
const actions = '[data-copy], [data-order], [data-handoff-prepare], [data-follow], [data-save]';

async function file(name) {
  const raw = await readFile(path.join(DIR, name));
  return name.endsWith('.gz') ? gunzipSync(raw) : raw;
}
async function fixture(name) {
  const [publication, reader, receiptRaw, raw] = await Promise.all([
    file(name + '-publication.json.gz'), file(name + '-reader.json.gz'),
    file(name + '-receipt.json'), file(name + '-bundle.json')
  ]);
  const receipt = JSON.parse(receiptRaw), bundle = JSON.parse(raw);
  return { name, publication, reader, receipt, raw, bundle,
    now: new Date(Date.parse(receipt.generated_at) + 60000).toISOString() };
}
function reseal(fixture, edit) {
  const receipt = structuredClone(fixture.receipt), bundle = structuredClone(fixture.bundle);
  edit(receipt, bundle);
  const raw = json(bundle);
  receipt.bundle = { sha256: sha(raw), bytes: raw.length, path: 'research-outcomes/' + sha(raw) + '.json' };
  return { receipt, raw };
}

export async function checkResearchOutcomes({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- frozen research follow-through: exact original cohorts, dated model observations, no private result authority');
  const state = page => page.evaluate(() => SCStock.researchOutcomes.status());
  const settled = page => page.waitForFunction(() => ['loaded', 'unavailable'].includes(SCStock.researchOutcomes.status().state));
  const text = page => page.locator('[data-outcome-body]').innerText();
  const reveal = async page => { await page.locator('[data-research-outcomes] > summary').click(); await settled(page); };
  const snapshot = page => page.evaluate(async () => {
    const hash = async value => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(value)))), byte => byte.toString(16).padStart(2, '0')).join('');
    return { data: await hash(SCStock.data), model: await hash(SCStock.model), storage: await hash(localStorage), morning: SCStock.observations.facts(),
      controls: [...document.querySelectorAll('[data-copy], [data-order], [data-handoff-prepare]')].map(node => ({ copy: node.getAttribute('data-copy'), order: node.getAttribute('data-order'), prepare: node.hasAttribute('data-handoff-prepare'), disabled: node.disabled })) };
  });
  async function setup(source, options = {}) {
    const requests = [], transport = { current: options.variant || source, held: null, release: null };
    const tab = await open(browser, base, options.canonical ? '/outcomes-canonical-control.json' : null, options.now || source.now, options.width || 1280, {
      theme: options.theme || 'dark', reducedMotion: 'reduce', lens: 'all', hash: options.hash || '#/explore/setting-up/KE',
      beforeLoad: async (page, context) => {
        await context.addCookies([{ name: 'research_private_cookie', value: PRIVATE, url: base }]);
        page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData(), headers: request.headers() }));
        await page.addInitScript(privateValue => {
          localStorage.setItem('research-outcomes-private-sentinel', privateValue);
          window.__outcomeRequests = [];
          const fetch = window.fetch;
          window.fetch = function(url, options = {}) {
            if (/\/research-outcomes(?:\.json|\/)/.test(String(url))) window.__outcomeRequests.push({ url: String(url), credentials: options.credentials,
              mode: options.mode, redirect: options.redirect, referrerPolicy: options.referrerPolicy, method: options.method || 'GET', body: options.body || null });
            return fetch.apply(this, arguments);
          };
        }, PRIVATE);
        await page.route('**/docs/reader.json', route => route.fulfill({ contentType: 'application/json', body: source.reader }));
        await page.route('**/outcomes-canonical-control.json', route => route.fulfill({ contentType: 'application/json', body: source.publication }));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: '{}' }));
        await page.route('**/research-outcomes.json', async route => {
          const current = transport.current;
          if (transport.held === 'receipt') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ status: current.receiptStatus || 200, contentType: 'application/json', body: typeof current.receipt === 'string' ? current.receipt : JSON.stringify(current.receipt) });
        });
        await page.route('**/research-outcomes/*.json', async route => {
          const current = transport.current;
          if (transport.held === 'bundle') await new Promise(resolve => { transport.release = resolve; });
          await route.fulfill({ status: current.bundleStatus || 200, contentType: 'application/json', body: current.raw });
        });
        if (options.beforeLoad) await options.beforeLoad(page, context);
      }
    });
    await tab.page.waitForFunction(() => SCStock.researchOutcomes && !!SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    await tab.page.locator('#morning-open').click();
    return { ...tab, requests, transport };
  }
  const fit = async (page, label) => check(label + ': journal fits phone/dialog without horizontal overflow', await page.locator('#morning-desk').evaluate(host => host.scrollWidth <= host.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
  const noActions = async (page, label) => eq(label + ': no order, copy, save, follow or personal draft is promoted', await page.locator('[data-research-outcomes]').locator(actions).count(), 0);
  const row = (page, ticker, cohort) => page.locator((cohort ? '[data-outcome-cohort="' + cohort + '"] ' : '') + '[data-outcome-row="' + ticker + '"]');
  const value = (page, ticker, field, cohort) => row(page, ticker, cohort).locator('[data-outcome-field="' + field + '"]').innerText();
  const capture = async (page, name, ticker) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, { recursive: true });
    await page.locator('[data-outcome-status]').evaluate(node => node.scrollIntoView({ block: 'start' }));
    await page.screenshot({ path: path.join(shotsDir, name + '.png') });
    if (ticker && await row(page, ticker).count()) {
      await row(page, ticker).first().evaluate(node => node.scrollIntoView({ block: 'start' }));
      await page.screenshot({ path: path.join(shotsDir, name + '-' + ticker + '.png') });
    }
  };
  const pending = await fixture('pending');
  for (const [width, theme, direct] of [[1280, 'dark', false], [390, 'light', false], [390, 'dark', true], [1280, 'light', true]]) {
    const label = width + '/' + theme, tab = await setup(pending, { width, theme, canonical: direct });
    const { page, context, requests, errors } = tab;
    try {
      eq(label + ': closed journal causes zero additional journal requests', journalRequests(requests).length, 0);
      eq(label + ': actual loaded bytes are authoritative', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(direct ? pending.publication : pending.reader));
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('234.56'); await page.locator('#morning-cash').focus();
      const before = await snapshot(page), requestCount = requests.length;
      await page.evaluate(() => {
        window.__outcomeCash = document.getElementById('morning-cash');
        window.__outcomeChart = document.querySelector('#detail .sc-chart svg');
        document.querySelector('[data-research-outcomes]').open = true;
      });
      await settled(page);
      eq(label + ': actual frozen producer cohort loads', (await state(page)).state, 'loaded');
      eq(label + ': all original admitted and refused rows remain ordered', await page.locator('[data-outcome-row]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-outcome-row'))), ['MG', 'KE', 'ZIM', 'SN', 'PSNL']);
      eq(label + ': cash node, value and editing focus survive optional load', await page.evaluate(() => [document.getElementById('morning-cash') === window.__outcomeCash, window.__outcomeCash.value, document.activeElement === window.__outcomeCash]), [true, '234.56', true]);
      eq(label + ': non-null existing chart stays mounted', await page.evaluate(() => !!window.__outcomeChart && document.querySelector('#detail .sc-chart svg') === window.__outcomeChart), true);
      eq(label + ': public model, authority, private store and actionable controls are unchanged', await snapshot(page), before);
      await noActions(page, label);
      if ((await state(page)).state !== 'loaded') continue;
      eq(label + ': KE uses the frozen one-share research quantity', await value(page, 'KE', 'original-shares'), '1');
      eq(label + ': PSNL uses the frozen three-share research quantity', await value(page, 'PSNL', 'original-shares'), '3');
      for (const ticker of ['KE', 'PSNL']) {
        check(label + ': ' + ticker + ' awaits observation rather than claims a trade', /pending|awaiting/i.test(await value(page, ticker, 'status')));
        check(label + ': ' + ticker + ' unknown outcome is not zero R', /unavailable|unknown|not established|pending|—/i.test(await value(page, ticker, 'r')) && !/^[+-]?0(?:\.0+)?\s*R?$/.test(await value(page, ticker, 'r')));
      }
      for (const ticker of ['MG', 'ZIM', 'SN']) check(label + ': original ' + ticker + ' refusal remains visible', /excluded|not eligible/i.test(await value(page, ticker, 'status')));
      const copy = await text(page);
      check(label + ': explicit daily-bar model and actual-cost uncertainty', /daily.bar/i.test(copy) && /actual.*(?:fees|costs)|fees.*unspecified/i.test(copy));
      check(label + ': no fabricated portfolio total or success metric', !/win rate|total profit|successful trade/i.test(copy) && /No broker execution, personal result, portfolio return/.test(copy));
      const outbound = journalRequests(requests);
      eq(label + ': lazy journal uses exactly its fixed receipt and bound digest', outbound.map(r => new URL(r.url).pathname), ['/docs/research-outcomes.json', '/docs/' + pending.receipt.bundle.path]);
      eq(label + ': no unrequested source-symbol or original-cohort fetch', requests.length - requestCount, 2);
      check(label + ': private values and cookies never travel with journal reads', outbound.every(r => r.method === 'GET' && !r.body && !r.headers.cookie && !r.headers.referer && !r.url.includes(PRIVATE)));
      eq(label + ': lazy transport omits credentials/referrer and refuses redirects', await page.evaluate(() => window.__outcomeRequests.map(r => [r.credentials, r.referrerPolicy, r.redirect, r.mode, r.method, r.body])), [['omit', 'no-referrer', 'error', 'same-origin', 'GET', null], ['omit', 'no-referrer', 'error', 'same-origin', 'GET', null]]);
      await fit(page, label); await capture(page, 'research-outcomes-pending-' + width + '-' + theme, 'KE');
      eq(label + ': valid journal has no page exceptions or transport errors', [...errors], []);
    } finally { await context.close(); }
  }

  const boundary = await setup(pending);
  try {
    const { page, transport } = boundary, original = await snapshot(page);
    await reveal(page);
    eq('boundary setup starts from valid genuine producer journal', (await state(page)).state, 'loaded');
    const change = edit => reseal(pending, edit);
    const common = (key, value) => change((r, b) => { r[key] = value; b[key] = structuredClone(value); });
    const bind = (key, value) => common('publication', { ...pending.receipt.publication, [key]: value });
    const rowChange = edit => change((r, b) => edit(b.cohorts[0].rows.find(x => x.ticker === 'KE'), b.cohorts[0], b, r));
    const cases = [
      ['canonical publication identity', bind('data_sha256', '0'.repeat(64))],
      ['actual reader byte identity', change((r, b) => {
        r.publication.reader_sha256 = b.publication.reader_sha256 = pending.receipt.publication.data_sha256;
        for (const cohort of b.cohorts) for (const row of cohort.rows) if (row.observation && !row.observation.carried)
          row.observation.publication.reader_sha256 = pending.receipt.publication.data_sha256;
      })],
      ['context identity', bind('context_sha256', '0'.repeat(64))],
      ['run identity', bind('run_id', 'different-research-source')],
      ['rules identity', bind('rules_version', '0'.repeat(12))],
      ['applicable session identity', bind('applicable_session', '2026-10-13')],
      ['complete supported policy', common('policy', { ...pending.receipt.policy, horizon_sessions: 6 })],
      ['future source clock', common('generated_at', '2099-01-01T12:00:00Z')],
      ['ordered cohort set identity', common('cohort_set_sha256', '0'.repeat(64))],
      ['complete row counts', common('counts', { ...pending.receipt.counts, rows: 0 })],
      ['embedded original raw byte identity', change((r, b) => { b.cohorts[0].source.raw += ' '; b.cohorts[0].source.bytes += 1; })],
      ['embedded original byte count', change((r, b) => { b.cohorts[0].source.bytes += 1; })],
      ['first prospective primary cohort', change((r, b) => { b.cohorts[0].primary = false; r.counts.primary_cohorts = b.counts.primary_cohorts = 0; })],
      ['cohort revision ordering', change((r, b) => { b.cohorts[0].revision = 2; })],
      ['original row evidence identity', rowChange(row => { row.evidence_id = '0'.repeat(64); })],
      ['complete original row membership', change((r, b) => { b.cohorts[0].rows.pop(); })],
      ['frozen research share count', rowChange(row => { row.model.original_shares = 2; })],
      ['no fabricated zero R for pending model', rowChange(row => { row.model.r = 0; })],
      ['no manufactured sold shares without fill', rowChange(row => { row.model.sold_shares = 0; })],
      ['required conditional-model limitations', change((r, b) => { b.limits = []; })],
      ['no executable order field', rowChange(row => { row.order_json = { symbol: 'KE', quantity: 1 }; })]
    ];
    for (const [name, variant] of cases) {
      transport.current = variant; await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
      eq(name + ': independently resealed invalid journal is refused', (await state(page)).state, 'unavailable');
      eq(name + ': invalid and previous rows are absent', await page.locator('[data-outcome-row]').count(), 0);
      eq(name + ': public/private state and authority remain untouched', await snapshot(page), original);
    }
    for (const [name, edit] of [
      ['path traversal', receipt => { receipt.bundle.path = '../private.json'; }],
      ['cross-origin digest path', receipt => { receipt.bundle.path = 'https://example.com/private.json'; }],
      ['declared bundle limit', receipt => { receipt.bundle.bytes = 2 * 1024 * 1024 + 1; }],
      ['exact raw digest', receipt => { receipt.bundle.sha256 = '0'.repeat(64); receipt.bundle.path = 'research-outcomes/' + receipt.bundle.sha256 + '.json'; }],
      ['actual versus declared length', receipt => { receipt.bundle.bytes -= 1; }]
    ]) {
      const receipt = structuredClone(pending.receipt); edit(receipt); transport.current = { receipt, raw: pending.raw };
      await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
      eq(name + ': invalid transport cannot attach', (await state(page)).state, 'unavailable');
      eq(name + ': no journal rows are rendered', await page.locator('[data-outcome-row]').count(), 0);
    }
    const bom = { receipt: structuredClone(pending.receipt), raw: Buffer.concat([Buffer.from([239, 187, 191]), pending.raw]) };
    bom.receipt.bundle.bytes = bom.raw.length; transport.current = bom;
    await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
    check('BOM-prefixed bytes fail the actual raw digest boundary', (await state(page)).state === 'unavailable' && /digest differs/.test((await state(page)).issue));
    transport.current = { receipt: ' '.repeat(16 * 1024 + 1), raw: pending.raw };
    await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
    check('receipt byte cap rejects before parsing oversized JSON', /size limit|declared size/.test((await state(page)).issue));
    await page.evaluate(() => {
      window.__outcomeNormalFetch = window.fetch;
      window.fetch = async function(url, options) {
        const response = await window.__outcomeNormalFetch.apply(this, arguments), pathname = new URL(url, location.href).pathname;
        const cap = window.__outcomeOversize === 'receipt' && pathname.endsWith('/research-outcomes.json') ? 16 * 1024
          : window.__outcomeOversize === 'bundle' && /\/research-outcomes\/[a-f0-9]{64}\.json$/.test(pathname) ? 2 * 1024 * 1024 : null;
        if (cap === null) return response;
        await response.arrayBuffer();
        return new Response(new ReadableStream({ start(controller) {
          controller.enqueue(new Uint8Array(cap)); controller.enqueue(new Uint8Array(1)); controller.close();
        } }), { headers: { 'content-length': '1' } });
      };
    });
    for (const role of ['receipt', 'bundle']) {
      transport.current = { ...pending, receipt: structuredClone(pending.receipt) };
      if (role === 'bundle') transport.current.receipt.bundle.bytes = 2 * 1024 * 1024;
      await page.evaluate(role => { window.__outcomeOversize = role; return SCStock.researchOutcomes.reload(); }, role); await settled(page);
      check(role + ': actual streamed cap precedes native buffering despite false header', /exceeds its declared size/.test((await state(page)).issue));
      eq(role + ': oversized response cannot render model observations', await page.locator('[data-outcome-row]').count(), 0);
    }
    await page.evaluate(() => { window.fetch = window.__outcomeNormalFetch; });
    for (const role of ['receipt', 'bundle']) {
      transport.current = { ...pending, [role + 'Status']: 404 };
      await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
      eq(role + ': optional file outage is explicit unavailable', (await state(page)).state, 'unavailable');
      eq(role + ': outage cannot mutate private/public state', await snapshot(page), original);
      eq(role + ': no old rows masquerade as a successful reload', await page.locator('[data-outcome-row]').count(), 0);
    }
    transport.current = pending; await page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(page);
    eq('explicit retry recovers original producer journal', (await state(page)).state, 'loaded');
    await noActions(page, 'recovered journal');
    eq('handled invalid source controls cause no page exceptions', [...boundary.errors], []);
  } finally { await boundary.context.close(); }
  const scenarioNames = ['observed', 'revised', 'missing', 'basis-conflict', 'not-filled', 'empty', 'red', 'cohort-revisions'];
  for (const name of scenarioNames) {
    const source = await fixture(name), tab = await setup(source, { width: 390, theme: 'light', hash: '#/explore' });
    const { page } = tab;
    try {
      const before = await snapshot(page);
      await reveal(page);
      eq(name + ': genuine producer observations load', (await state(page)).state, 'loaded');
      eq(name + ': complete original cohorts retain exact order', await page.locator('[data-outcome-cohort]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-outcome-cohort'))), source.bundle.cohorts.map(c => c.source.sha256));
      eq(name + ': all original rows survive including excluded examples', await page.locator('[data-outcome-row]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-outcome-row'))), source.bundle.cohorts.flatMap(c => c.rows.map(r => r.ticker)));
      if ((await state(page)).state !== 'loaded') continue;
      if (name === 'observed') {
        eq('one-share model exits its only whole share', await value(page, 'COIL', 'sold-shares'), '1');
        eq('one-share model has zero remaining hypothetical shares', await value(page, 'COIL', 'remaining-shares'), '0');
        eq('known model open uses the frozen entry price', await value(page, 'COIL', 'entry'), '$55.31');
        eq('whole-share exit R uses original stop risk', await value(page, 'COIL', 'r'), '2.26 R');
        check('unknown first-thirty-minute crossing stays uncertain', /uncertain/i.test(await value(page, 'RONE', 'status')));
        eq('uncertain fill establishes no entry or zero-valued result', await Promise.all(['entry', 'sold-shares', 'remaining-shares', 'r'].map(field => value(page, 'RONE', field))), ['Not established', 'Not established', 'Not established', 'Not established']);
        check('known unexited model remains hypothetical open', /model open/i.test(await value(page, 'RTHR', 'status')));
        eq('open model preserves its whole hypothetical share', await value(page, 'RTHR', 'remaining-shares'), '1');
        eq('open model does not acquire a resolved R', await value(page, 'RTHR', 'r'), 'Not established');
      } else if (name === 'revised') {
        eq('same-close changed low invokes stop-first model loss', await value(page, 'COIL', 'r'), '-1.00 R');
        check('changed OHLC day is explicitly called a revision', /Revised daily observations:.*2026-10-12/s.test(await row(page, 'COIL').innerText()));
        check('revised clip cannot imply an earlier snapshot was overwritten', /does not rewrite earlier snapshots/.test(await row(page, 'COIL').innerText()));
      } else if (name === 'missing') {
        check('absent entry-session evidence is not a zero-return trade', /missing/i.test(await value(page, 'COIL', 'status')));
        eq('missing evidence has no fabricated R', await value(page, 'COIL', 'r'), 'Not established');
        check('missing dated market coverage remains explicit', /Missing completed sessions:.*2026-10-12/s.test(await row(page, 'COIL').innerText()));
      } else if (name === 'basis-conflict') {
        check('changed provider/feed basis refuses cross-basis replay', /basis conflict/i.test(await value(page, 'COIL', 'status')));
        eq('conflicting input basis yields no R', await value(page, 'COIL', 'r'), 'Not established');
      } else if (name === 'not-filled') {
        check('never-triggered daily bar is no model fill', /No model fill/.test(await value(page, 'COIL', 'status')));
        check('open beyond limit remains uncertain', /uncertain/i.test(await value(page, 'RONE', 'status')));
        check('intraday trigger-stop ordering remains uncertain', /uncertain/i.test(await value(page, 'RTHR', 'status')));
        for (const ticker of ['COIL', 'RONE', 'RTHR']) eq(ticker + ': non-established fill remains without numeric R', await value(page, ticker, 'r'), 'Not established');
      } else if (name === 'empty') {
        check('zero-row source remains visibly recorded', /Zero-row cohort retained/.test(await text(page)));
        eq('empty journal does not invent model rows', await page.locator('[data-outcome-row]').count(), 0);
      } else if (name === 'red') {
        check('red market cohort explicitly retains all original refusals', (await page.locator('[data-outcome-field="status"]').allTextContents()).every(x => /excluded/i.test(x)));
        check('red cohort claims no resolved R', (await page.locator('[data-outcome-field="r"]').allTextContents()).every(x => x === 'Not established'));
      } else {
        eq('repeated source session keeps both prospective and later capture', source.bundle.cohorts.length, 2);
        eq('only the actual first pre-entry capture is primary', source.bundle.cohorts.map(c => c.primary), [true, false]);
        eq('both original generations remain distinct labelled cohorts', await page.locator('[data-outcome-cohort] > h4').allTextContents(), ['Primary · first pre-entry capture', 'Revision 2 · retained separately']);
        check('after-entry second capture cannot masquerade as prospective', /after entry.*retrospective/i.test(await page.locator('[data-outcome-cohort]').nth(1).innerText()));
        eq('repeated cohort rows are not collapsed into one winning population', await page.locator('[data-outcome-row]').count(), 10);
      }
      eq(name + ': load never changes broker reports, public model or order authority', await snapshot(page), before);
      await noActions(page, name); await fit(page, name);
      check(name + ': observation label remains dated and not a quote check', /Dated observation snapshot.*not a current price check/s.test(await page.locator('[data-outcome-status]').innerText()));
      await capture(page, 'research-outcomes-' + name + '-390-light', name === 'empty' || name === 'red' ? null : 'COIL');
      if (name === 'observed' && shotsDir) for (const ticker of ['RONE', 'RTHR']) { await row(page, ticker).evaluate(node => node.scrollIntoView({ block: 'start' })); await page.screenshot({ path: path.join(shotsDir, 'research-outcomes-observed-390-light-' + ticker + '.png') }); }
      if (['observed', 'revised'].includes(name) && shotsDir) { await row(page, 'COIL').locator('[data-outcome-field=entry]').evaluate(node => node.scrollIntoView({ block: 'start' })); await page.screenshot({ path: path.join(shotsDir, 'research-outcomes-' + name + '-390-light-result.png') }); }
      eq(name + ': valid model has no page exceptions', [...tab.errors], []);
    } finally { await tab.context.close(); }
  }

  const observed = await fixture('observed'), evidence = await setup(observed, { hash: '#/explore' });
  try {
    await reveal(evidence.page);
    const edits = [
      ['whole-share R arithmetic', row => { row.model.r += 0.01; }],
      ['whole-share sold reconciliation', row => { row.model.sold_shares = 0; }],
      ['resolved remaining quantity', row => { row.model.remaining_shares = 1; }],
      ['observation input basis', row => { row.observation.basis.feed = 'other'; }],
      ['observation source anchor', row => { row.observation.anchor.close += 0.01; }],
      ['fresh observation publication', row => { row.observation.publication.data_sha256 = '0'.repeat(64); }],
      ['carried evidence cannot postdate observation publication', row => { row.observation.carried = true; row.observation.publication.published_at = '2026-10-12T22:31:00+00:00'; }],
      ['fresh bar session attribution', row => { row.observation.bars[0].from_session = '2026-10-09'; }],
      ['finite consistent OHLC', row => { row.observation.bars[0].l = row.observation.bars[0].h + 1; }],
      ['bounded five-session replay', row => { row.model.day = row.model.sessions = 6; }],
      ['revised-day evidence', row => { row.observation.changed_dates = ['2026-10-12']; }]
    ];
    for (const [name, edit] of edits) {
      evidence.transport.current = reseal(observed, (r, b) => edit(b.cohorts[0].rows.find(row => row.ticker === 'COIL')));
      await evidence.page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(evidence.page);
      eq(name + ': coherently resealed invalid evidence refuses attachment', (await state(evidence.page)).state, 'unavailable');
      eq(name + ': rejected evidence leaves no result rows', await evidence.page.locator('[data-outcome-row]').count(), 0);
    }
    evidence.transport.current = reseal(observed, (r, b) => { b.cohorts[0].rows[0].model.reason = '<img src=x onerror="window.__outcomeInjected=true">' + 'X'.repeat(256); });
    await evidence.page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(evidence.page);
    eq('bounded source explanation remains valid inert text', (await state(evidence.page)).state, 'loaded');
    check('HTML-like source text is visible without becoming executable HTML', (await text(evidence.page)).includes('<img src=x onerror=') && await evidence.page.locator('[data-outcome-body] img').count() === 0 && !await evidence.page.evaluate(() => window.__outcomeInjected));
    await evidence.page.setViewportSize({ width: 390, height: 900 }); await fit(evidence.page, 'unbroken bounded source text');
    await noActions(evidence.page, 'inert source text');
    eq('source boundary controls do not produce browser exceptions', [...evidence.errors], []);
  } finally { await evidence.context.close(); }

  const replacement = await fixture('empty'), race = await setup(pending);
  try {
    race.transport.held = 'bundle'; await race.page.locator('[data-research-outcomes] > summary').click();
    for (let i = 0; i < 100 && !race.transport.release; i++) await race.page.waitForTimeout(20);
    check('late-response control holds the actual requested old journal', !!race.transport.release);
    await race.page.evaluate(async raw => { const next = JSON.parse(raw); SCStock.render(next, new Date(SCStock.now)); await SCStock.observations.bind(next, raw); }, replacement.publication.toString('utf8'));
    const release = race.transport.release; race.transport.held = null; if (release) release(); await settled(race.page);
    eq('late old journal cannot attach to replacement publication', (await state(race.page)).state, 'unavailable');
    eq('late source leaves no stale model outcomes', await race.page.locator('[data-outcome-row]').count(), 0);
    eq('replacement canonical digest remains authoritative', await race.page.evaluate(() => SCStock.observations.facts().canonicalHash), sha(replacement.publication));
  } finally { if (race.transport.release) race.transport.release(); await race.context.close(); }
  const stalled = await setup(pending);
  try {
    stalled.transport.held = 'bundle';
    const began = Date.now(); await stalled.page.locator('[data-research-outcomes] > summary').click(); await settled(stalled.page);
    const elapsed = Date.now() - began;
    check('actual stalled bundle stops at its bounded 15-second deadline', /timed out after 15 seconds/.test((await state(stalled.page)).issue) && elapsed >= 14500 && elapsed < 25000, elapsed);
    eq('timed-out read exposes no stale model rows', await stalled.page.locator('[data-outcome-row]').count(), 0);
    check('timeout leaves an enabled explicit retry', await stalled.page.locator('[data-outcome-reload]').isEnabled());
    const release = stalled.transport.release; stalled.transport.held = null; if (release) release();
    await stalled.page.evaluate(() => SCStock.researchOutcomes.reload()); await settled(stalled.page);
    eq('retry after actual deadline loads the exact original journal', (await state(stalled.page)).state, 'loaded');
    await noActions(stalled.page, 'bounded deadline retry');
  } finally { if (stalled.transport.release) stalled.transport.release(); await stalled.context.close(); }
  const cryptoTab = await setup(pending);
  try {
    await cryptoTab.page.evaluate(() => Object.defineProperty(window, 'crypto', { configurable: true, value: undefined }));
    await reveal(cryptoTab.page);
    eq('missing exact-byte verification refuses journal', (await state(cryptoTab.page)).state, 'unavailable');
    eq('missing crypto causes zero unverified source requests', journalRequests(cryptoTab.requests).length, 0);
    await noActions(cryptoTab.page, 'missing crypto');
  } finally { await cryptoTab.context.close(); }
}
