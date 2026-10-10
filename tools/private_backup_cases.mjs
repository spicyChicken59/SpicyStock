/* Local backup controls over frozen producer publications. All broker facts,
   legacy profiles and downloaded files are explicitly synthetic private input.
   Nothing uses a real browser profile, public-data edits or provider calls. */
import { readFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { tmpdir } from 'node:os';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const KEY = 'spicystock:handoff:v1', MAX_BYTES = 1048576;
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const saved = page => page.evaluate(() => SCStock.handoff.list());
const stored = page => page.evaluate(key => localStorage.getItem(key), KEY);
const writes = page => page.evaluate(() => window.__backupWrites);
const status = page => page.locator('[data-handoff-backup-status]').textContent();
const set = async (page, values) => { for (const [key, value] of Object.entries(values)) await field(page, key).fill(value); };
async function producer() {
  const stem = path.join(ROOT, 'tests/fixtures/stop-research/current');
  const [canonical, reader, receiptRaw, bundleRaw] = await Promise.all([
    readFile(stem + '-publication.json.gz').then(gunzipSync), readFile(stem + '-reader.json.gz').then(gunzipSync), readFile(stem + '-receipt.json'), readFile(stem + '-bundle.json')
  ]);
  const receipt = JSON.parse(receiptRaw);
  return { canonical, reader, receiptRaw, bundleRaw, receipt, now: new Date(Date.parse(receipt.timing.generated_at) + 60000).toISOString() };
}
async function legacy() {
  const source = await readFile(path.join(ROOT, 'tools/handoff_model_cases.mjs'), 'utf8');
  return ['LEGACY_RAW', 'LEGACY_V2_RAW'].map(name => {
    const match = source.match(new RegExp('^const ' + name + ' = ("(?:[^"\\\\]|\\\\.)*");$', 'm'));
    if (!match) throw Error('Missing original module-produced private control: ' + name);
    return JSON.parse(match[1]);
  });
}
async function reveal(page) {
  if (!await page.locator('#morning-desk').evaluate(node => node.open)) await page.locator('#morning-open').click();
  if (!await page.locator('#morning-handoffs').evaluate(node => node.open)) await page.locator('#morning-handoffs > summary').click();
  if (!await page.locator('[data-handoff-backup]').evaluate(node => node.open)) await page.locator('[data-handoff-backup] > summary').click();
}
async function chooseFile(page, raw, name = 'SYNTHETIC-private-backup.json') {
  await page.locator('[data-handoff-backup-file]').setInputFiles({ name, mimeType: 'application/json', buffer: Buffer.isBuffer(raw) ? raw : Buffer.from(raw, 'utf8') });
  await page.waitForFunction(() => {
    const s = document.querySelector('[data-handoff-backup-status]');
    return s && s.textContent && !/reading|validating|loading/i.test(s.textContent);
  });
}
async function confirm(page) {
  await page.locator('[data-handoff-backup-confirm]').click();
  await page.waitForFunction(() => {
    const s = document.querySelector('[data-handoff-backup-status]');
    return s && !/restoring|saving/i.test(s.textContent);
  });
}

export async function checkPrivateBackup({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- private backup: synthetic saved facts, exact bytes, explicit empty-only restore');
  const fixture = await producer(), originals = await legacy(), scratch = await mkdtemp(path.join(tmpdir(), 'spicystock-private-backup-browser-'));
  const launch = async ({ seed = null, width = 1280, theme = 'dark', noPublication = false } = {}) => {
    const requests = [], responses = [];
    const tab = await open(browser, base, null, fixture.now, width, { theme, lens: 'all', reducedMotion: 'reduce', beforeLoad: async (page, context) => {
      page.setDefaultTimeout(5000);
      await context.addInitScript(({ now, seed, key }) => {
        const NativeDate = Date; window.__backupClock = Date.parse(now);
        window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [window.__backupClock])); } static now() { return window.__backupClock; } };
        if (seed !== null) localStorage.setItem(key, seed);
        const originalSet = Storage.prototype.setItem, originalGet = Storage.prototype.getItem, originalRemove = Storage.prototype.removeItem;
        window.__backupWrites = 0; window.__backupFault = ''; window.__backupWritten = false;
        Storage.prototype.setItem = function (name, value) { if (name === key) { window.__backupWrites++; if (window.__backupFault === 'quota') throw new DOMException('Synthetic backup quota control', 'QuotaExceededError'); window.__backupWritten = true; } return originalSet.call(this, name, value); };
        Storage.prototype.getItem = function (name) { const raw = originalGet.call(this, name); if (name === key && window.__backupFault === 'readback' && window.__backupWritten) { window.__backupWritten = false; return raw + ' '; } return raw; };
        Storage.prototype.removeItem = function (name) { if (name === key) { window.__backupWrites++; window.__backupWritten = false; } return originalRemove.call(this, name); };
        window.__backupFileReads = [];
        const originalBuffer = Blob.prototype.arrayBuffer;
        Blob.prototype.arrayBuffer = function () { window.__backupFileReads.push(this.size); return originalBuffer.call(this); };
        window.__backupCopies = 0;
        Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { window.__backupCopies++; } } });
      }, { now: fixture.now, seed, key: KEY });
      context.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }));
      page.on('response', response => responses.push({ url: response.url(), status: response.status() }));
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) { await route.fulfill({ contentType: url.hostname === 'fonts.googleapis.com' ? 'text/css' : 'application/json', body: url.hostname === 'fonts.googleapis.com' ? '' : '{}' }); return; }
        if (url.pathname === '/docs/reader.json') { await route.fulfill({ status: noPublication ? 503 : 200, contentType: 'application/json', body: noPublication ? '{"synthetic":"startup unavailable"}' : fixture.reader }); return; }
        if (url.pathname === '/docs/morning.json') { await route.fulfill({ contentType: 'application/json', body: '{}' }); return; }
        if (url.pathname === '/docs/stop-research.json') { await route.fulfill({ contentType: 'application/json', body: fixture.receiptRaw }); return; }
        if (url.pathname.startsWith('/docs/stop-research/')) { await route.fulfill({ contentType: 'application/json', body: fixture.bundleRaw }); return; }
        await route.continue();
      });
    } });
    if (!noPublication) await tab.page.waitForFunction(() => SCStock.observations.facts().recordHash && !SCStock.observations.facts().pending);
    await reveal(tab.page);
    return { ...tab, requests, responses, noPublication };
  };
  const capture = async (page, name, anchor = '[data-handoff-backup]') => { if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator(anchor).scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, name + '.png') }); } };
  let downloadIndex = 0;
  const download = async page => {
    const waiting = page.waitForEvent('download'); await page.locator('[data-handoff-backup-download]').click();
    const file = await waiting, target = path.join(scratch, String(downloadIndex++) + '.json');
    await file.saveAs(target);
    return { raw: await readFile(target), name: file.suggestedFilename() };
  };
  const authority = page => page.evaluate(() => ({ data: JSON.stringify(SCStock.data), model: JSON.stringify(SCStock.model), following: localStorage.getItem('spicystock:following:v1'), cash: document.getElementById('morning-cash').value }));
  const privateOnly = async (tab, start, name) => {
    eq(name + ': no backup, filename or report reaches HTTP', tab.requests.slice(start), []);
    eq(name + ': backup and restore never copy an order', await tab.page.evaluate(() => window.__backupCopies), 0);
    // This explicit no-publication control returns one503. Its byte-reader
    // preflight cancels that same body. Budget exactly those two paired events;
    // unrelated console failures/cancellations remain failures.
    let consoleBudget = tab.noPublication && tab.responses.filter(response => response.url === base + '/docs/reader.json' && response.status === 503).length === 1 ? 1 : 0;
    let abortBudget = consoleBudget;
    const errors = Array.from(tab.errors).filter(error => {
      if (consoleBudget && error === 'console: Failed to load resource: the server responded with a status of 503 (Service Unavailable)') { consoleBudget--; return false; }
      if (abortBudget && error === 'request failed: ' + base + '/docs/reader.json net::ERR_ABORTED') { abortBudget--; return false; }
      return true;
    });
    eq(name + ': no unexpected browser error', errors, []);
  };
  const run = async (name, fn) => { try { await fn(); } catch (error) { check('private backup ' + name + ': workflow completes', false, error.stack); } };
  let mixedRaw = null;

  try {
    await run('normal export and mixed roundtrip', async () => {
      const donor = await launch({ seed: originals[1] }), { page } = donor;
      try {
        eq('donor: opening backup does not migrate exact original v2 bytes', await stored(page), originals[1]);
        eq('donor: backup access performs zero storage writes', await writes(page), 0);
        await page.locator('[data-stop-research] > summary').click(); await page.waitForFunction(() => SCStock.stopResearch.status().state === 'loaded');
        await page.locator('[data-stop-report="KE"]').click();
        await set(page, { submitted_quantity: '9', filled_quantity: '7', average_price: '31.234567', exited_quantity: '3', entry_fees: '0.11' });
        await page.locator('[data-handoff-save]').click(); await page.waitForFunction(() => SCStock.handoff.list().length === 2);
        mixedRaw = await stored(page);
        eq('donor: explicit model writer produced planned and independent private kinds', (await saved(page)).map(item => item.kind), ['planned_handoff', 'independent_research']);
        const before = await authority(page), count = await writes(page), start = donor.requests.length;
        await field(page, 'average_price').fill('30.99'); await field(page, 'average_price').focus();
        await page.evaluate(() => { window.__backupDirty = document.querySelector('[data-handoff-field="average_price"]'); });
        const exported = await download(page);
        eq('export: healthy backup is exact saved bytes excluding unsaved correction', exported.raw.toString('utf8'), mixedRaw);
        eq('export: read/download never writes private storage', [await writes(page), await stored(page)], [count, mixedRaw]);
        eq('export: dirty node/value remains unchanged', await field(page, 'average_price').evaluate(node => [node === window.__backupDirty, node.value]), [true, '30.99']);
        check('export: disclosure identifies private broker facts and absence of cloud backup', /private|broker/i.test(await page.locator('[data-handoff-backup]').textContent()) && /no cloud|not.*cloud/i.test(await page.locator('[data-handoff-backup]').textContent()));
        eq('export: public/model/following/cash authority is unchanged', await authority(page), before);
        await privateOnly(donor, start, 'donor export');
      } finally { await donor.context.close(); }
      if (!mixedRaw) return;
      for (const [width, theme] of [[390, 'light'], [1280, 'dark']]) {
        const tab = await launch({ width, theme }), { page } = tab, name = 'roundtrip ' + width + '/' + theme;
        try {
          const start = tab.requests.length, before = await authority(page);
          eq(name + ': absent store begins empty with no backup invented', [await stored(page), await writes(page)], [null, 0]);
          let absentDownloads = 0;
          const countDownload = () => { absentDownloads++; }; page.on('download', countDownload);
          await page.locator('[data-handoff-backup-download]').click();
          await page.waitForFunction(() => document.querySelector('[data-handoff-backup]').dataset.handoffBackupState === 'unavailable');
          eq(name + ': absent store cannot invent a healthy downloaded backup', absentDownloads, 0); page.off('download', countDownload);
          await chooseFile(page, mixedRaw);
          eq(name + ': preview stores nothing', [await stored(page), await writes(page)], [null, 0]);
          check(name + ': preview shows both private kinds and original source dates', /planned|handoff/i.test(await page.locator('[data-handoff-backup-preview]').textContent()) && /independent/i.test(await page.locator('[data-handoff-backup-preview]').textContent()) && /2026-09-10|Sep 10/.test(await page.locator('[data-handoff-backup-preview]').textContent()) && /2026-10-09|Oct 9/.test(await page.locator('[data-handoff-backup-preview]').textContent()));
          await capture(page, 'private-backup-preview-' + width + '-' + theme);
          await capture(page, 'private-backup-confirm-' + width + '-' + theme, '[data-handoff-backup-confirm]');
          await page.locator('[data-handoff-backup-cancel]').click();
          eq(name + ': explicit preview cancellation stores nothing', [await stored(page), await writes(page)], [null, 0]);
          eq(name + ': cancel withdraws restore authority', await page.locator('[data-handoff-backup-confirm]').isVisible(), false);
          await chooseFile(page, mixedRaw);
          await page.locator('[data-handoff-backup-confirm]').focus(); await page.keyboard.press('Enter');
          await page.waitForFunction(() => document.querySelector('[data-handoff-backup]').dataset.handoffBackupState === 'restored');
          eq(name + ': keyboard restore leaves focus on its persistent status', await page.locator('[data-handoff-backup-status]').evaluate(node => document.activeElement === node), true);
          eq(name + ': explicit restore retains every original byte', await stored(page), mixedRaw);
          eq(name + ': exact export roundtrip retains whitespace/version/facts', (await download(page)).raw.toString('utf8'), mixedRaw);
          const items = await saved(page);
          eq(name + ': both restored items preserve original terms/source/report identity', items, JSON.parse(mixedRaw).items);
          const independent = items.find(item => item.kind === 'independent_research');
          eq(name + ': restored independent unknown exit price/cost/time stay unknown', [independent.report.average_exit_price, independent.report.exit_fees, independent.report.exited_at], [null, null, null]);
          eq(name + ': restored independent gains no plan/draft/readback/copy authority', await page.evaluate(id => { const item = SCStock.handoff.find(id); return [!!item.plan, !!item.draft, SCStock.handoff.readback(item), SCStock.handoff.copy(id).ok]; }, independent.id), [false, false, '', false]);
          const planned = items.find(item => item.kind === 'planned_handoff');
          eq(name + ': restored archived planned source cannot bypass current copy guard', await page.evaluate(id => SCStock.handoff.copy(id).ok, planned.id), false);
          eq(name + ': restore changes no public/model/following/cash authority', await authority(page), before);
          await capture(page, 'private-backup-restored-' + width + '-' + theme);
          check(name + ': disclosure fits phone/desktop', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth + 1));
          await privateOnly(tab, start, name);
        } finally { await tab.context.close(); }
      }
    });

    await run('asynchronous restore preserves deliberate focus move', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      const tab = await launch(), { page } = tab;
      try {
        await chooseFile(page, mixedRaw);
        await page.evaluate(key => { window.__backupLockHeld = false; navigator.locks.request(key, () => { window.__backupLockHeld = true; return new Promise(resolve => { window.__releaseBackupLock = resolve; }); }); }, KEY);
        await page.waitForFunction(() => window.__backupLockHeld);
        await page.locator('[data-handoff-backup-confirm]').focus(); await page.locator('[data-handoff-backup-confirm]').click();
        await page.waitForFunction(() => document.querySelector('[data-handoff-backup]').dataset.handoffBackupState === 'restoring');
        await page.locator('[data-handoff-backup] > summary').focus();
        await page.evaluate(() => window.__releaseBackupLock());
        await page.waitForFunction(() => document.querySelector('[data-handoff-backup]').dataset.handoffBackupState === 'restored');
        eq('async restore: completed restore cannot steal a deliberate focus move', await page.locator('[data-handoff-backup] > summary').evaluate(node => document.activeElement === node), true);
        eq('async restore: queued explicit action still restores exact bytes', await stored(page), mixedRaw);
      } finally { await tab.context.close(); }
    });

    await run('legacy byte preservation', async () => {
      for (const [index, raw] of originals.entries()) {
        // Exact original legacy model output, with preserved surrounding whitespace.
        const bytes = '\n  ' + raw + '\n', tab = await launch(), { page } = tab;
        try {
          await chooseFile(page, bytes); eq('legacy v' + (index + 1) + ': preview never writes/migrates', [await stored(page), await writes(page)], [null, 0]);
          await confirm(page);
          eq('legacy v' + (index + 1) + ': restore preserves version and all original bytes', await stored(page), bytes);
          eq('legacy v' + (index + 1) + ': read/export remains byte-identical without migration', (await download(page)).raw.toString('utf8'), bytes);
          eq('legacy v' + (index + 1) + ': original planned terms survive restore', (await saved(page))[0].plan, JSON.parse(raw).items[0].plan);
          const count = await writes(page); await page.reload(); await page.waitForFunction(() => document.documentElement.hasAttribute('data-ss-rendered')); await reveal(page);
          eq('legacy v' + (index + 1) + ': normal loading still preserves bytes', await stored(page), bytes);
          // Init scripts re-establish the per-page counter; no post-load write is allowed.
          eq('legacy v' + (index + 1) + ': no storage rewrite on read', await writes(page), 0);
          check('legacy v' + (index + 1) + ': explicit restore made exactly one write', count === 1);
        } finally { await tab.context.close(); }
      }
    });

    await run('dirty and transient restore refusal', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      const tab = await launch(), { page } = tab;
      try {
        await page.locator('[data-stop-research] > summary').click(); await page.waitForFunction(() => SCStock.stopResearch.status().state === 'loaded');
        await page.locator('[data-stop-report="KE"]').click();
        await set(page, { submitted_quantity: '4', filled_quantity: '3', average_price: '31.987654' }); await field(page, 'average_price').focus();
        await page.evaluate(() => { window.__transientBackupInput = document.querySelector('[data-handoff-field="average_price"]'); });
        // Local selection and preview completion must not move focus or rebuild the editor.
        await chooseFile(page, mixedRaw);
        eq('dirty: preview preserves exact field node/value/focus', await field(page, 'average_price').evaluate(node => [node === window.__transientBackupInput, node.value, document.activeElement === node]), [true, '31.987654', true]);
        await confirm(page);
        eq('dirty: actual restore cannot replace an unsaved new report', [await stored(page), await writes(page)], [null, 0]);
        check('dirty: refusal explains saving/cancelling local edits', /unsaved|save|cancel|discard/i.test(await status(page)));
        eq('dirty: rejected restore preserves entered actual facts', await field(page, 'average_price').inputValue(), '31.987654');
        await page.locator('[data-handoff-backup-cancel]').click();
        eq('dirty: cancelling file preview does not cancel the report editor', [await page.locator('#morning-handoffs').getAttribute('data-handoff-mode'), await field(page, 'filled_quantity').inputValue()], ['independent-unsaved', '3']);
        await page.locator('[data-handoff-cancel]').click();
        await chooseFile(page, mixedRaw); await confirm(page);
        eq('dirty: deliberate report discard then restore succeeds', await stored(page), mixedRaw);
        const prior = await stored(page), count = await writes(page);
        if (!await page.locator('[data-handoff-report]').evaluate(node => node.open)) await page.locator('[data-handoff-report] > summary').click();
        await field(page, 'average_price').fill('30.25'); await field(page, 'average_price').focus();
        await page.evaluate(() => { window.__savedBackupInput = document.querySelector('[data-handoff-field="average_price"]'); });
        await chooseFile(page, originals[0]);
        eq('occupied: preview refuses overwrite and preserves exact saved bytes', [await stored(page), await writes(page)], [prior, count]);
        eq('occupied: existing records cannot acquire restore confirmation', await page.locator('[data-handoff-backup-confirm]').isVisible(), false);
        eq('occupied: file rejection preserves exact dirty report node/value/focus', await field(page, 'average_price').evaluate(node => [node === window.__savedBackupInput, node.value, document.activeElement === node]), [true, '30.25', true]);
        check('occupied: refusal identifies nonempty destination', /empty|existing|occupied|already|saved records/i.test(await status(page)));
      } finally { await tab.context.close(); }
    });

    await run('malformed and bounded local files', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      const tab = await launch(), { page } = tab;
      try {
        const valid = JSON.parse(mixedRaw), independent = valid.items.find(item => item.kind === 'independent_research');
        // Invalid bytes inside an otherwise valid JSON string must reject;
        // a forgiving decoder would yield valid JSON containing U+FFFD.
        const invalidText = Buffer.from(mixedRaw), instruction = Buffer.from(valid.items[0].plan.exit_schedule[0].instruction);
        const instructionAt = invalidText.indexOf(instruction);
        if (instructionAt < 0) throw Error('Original planned instruction missing from exact backup');
        invalidText[instructionAt] = 255;
        const mutations = [
          ['invalid JSON', '{'], ['unknown future version', JSON.stringify({ ...valid, version: 99 })],
          ['emergency recovery is not a healthy backup', JSON.stringify({ prior: mixedRaw, proposed: mixedRaw })],
          ['duplicate original ID', JSON.stringify({ version: 3, items: [independent, independent] })],
          ['unknown envelope field', JSON.stringify({ ...valid, cloud_sync: true })],
          ['inconsistent actual fills', JSON.stringify({ version: 3, items: [{ ...independent, report: { ...independent.report, filled_quantity: 10 } }] })],
          ['report-only cannot acquire draft fields', JSON.stringify({ version: 3, items: [{ ...independent, draft: valid.items[0].draft }] })],
          ['BOM-prefixed file', Buffer.concat([Buffer.from([239, 187, 191]), Buffer.from(mixedRaw)])],
          ['invalid UTF8 file', Buffer.concat([Buffer.from(mixedRaw), Buffer.from([255])])],
          ['invalid UTF8 inside valid JSON string', invalidText]
        ];
        for (const [name, bad] of mutations) {
          await chooseFile(page, bad, 'SYNTHETIC-' + name.replaceAll(' ', '-') + '.json');
          eq(name + ': rejected file performs zero writes', [await stored(page), await writes(page)], [null, 0]);
          eq(name + ': rejected file offers no restore confirmation', await page.locator('[data-handoff-backup-confirm]').isVisible(), false);
          eq(name + ': invalid preview cannot poison readable destination status', await page.evaluate(() => SCStock.handoff.status().available), true);
        }
        const tooMany = Array.from({ length: 101 }, (_, index) => { const item = structuredClone(independent); item.source.evidence.id = index.toString(16).padStart(64, '0'); item.id = item.source.publication.data_sha256 + ':' + item.source.evidence.id; return item; });
        await chooseFile(page, JSON.stringify({ version: 3, items: tooMany }));
        eq('101 distinct valid-shaped items: count cap refuses restore', [await stored(page), await page.locator('[data-handoff-backup-confirm]').isVisible()], [null, false]);
        const oversized = Buffer.concat([Buffer.from(mixedRaw), Buffer.alloc(MAX_BYTES + 1 - Buffer.byteLength(mixedRaw), 32)]);
        await page.evaluate(() => { window.__backupFileReads = []; });
        await chooseFile(page, oversized);
        eq('oversized otherwise valid JSON: refuses without private writes', [await stored(page), await writes(page)], [null, 0]);
        eq('oversized file: known-size refusal reads no file bytes', await page.evaluate(() => window.__backupFileReads), []);
        check('oversized file: no local read exceeds bounded sentinel bytes', await page.evaluate(max => window.__backupFileReads.every(size => size <= max + 1), MAX_BYTES));
        await chooseFile(page, mixedRaw);
        eq('invalid then valid: healthy preview remains available without writes', [await stored(page), await writes(page), await page.locator('[data-handoff-backup-confirm]').isVisible()], [null, 0, true]);
      } finally { await tab.context.close(); }
    });

    await run('CAS, quota and readback recovery', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      const tab = await launch(), { page, context } = tab;
      try {
        const preview = await page.evaluate(raw => { const result = SCStock.handoff.previewBackup(raw); window.__backupCasPreview = result.preview; return { ok: result.ok }; }, mixedRaw);
        check('CAS: valid empty destination preview is available', preview.ok);
        const peer = await context.newPage(); await peer.goto(base + '/docs/index.html'); await peer.waitForFunction(() => !!SCStock.handoff?.restoreBackup);
        const peerResult = await peer.evaluate(async raw => { const p = SCStock.handoff.previewBackup(raw); return SCStock.handoff.restoreBackup(p.preview); }, originals[0]);
        check('CAS: real second browser tab restores under its lock', peerResult.ok);
        const prior = await stored(page);
        const result = await page.evaluate(() => SCStock.handoff.restoreBackup(window.__backupCasPreview));
        eq('CAS: old null-destination preview cannot overwrite second tab', [result.ok, await stored(page)], [false, prior]);
        await peer.close();
      } finally { await context.close(); }
      for (const fault of ['quota', 'readback']) {
        const empty = '\n {"version":2,"items":[]} \n', tab = await launch({ seed: empty }), { page } = tab;
        try {
          await chooseFile(page, mixedRaw);
          await page.evaluate(fault => { window.__backupFault = fault; }, fault);
          await confirm(page);
          await page.evaluate(() => { window.__backupFault = ''; });
          eq(fault + ': failed restore preserves exact original empty-envelope bytes', await stored(page), empty);
          eq(fault + ': recovery keeps exact prior/proposed without selecting one', await page.evaluate(() => SCStock.handoff.recovery()), { prior: empty, proposed: mixedRaw });
          eq(fault + ': emergency recovery remains a separate visible download', await page.locator('[data-handoff-recovery]').isVisible(), true);
          await chooseFile(page, mixedRaw); await confirm(page);
          eq(fault + ': explicit retry with healthy storage preserves exact backup', await stored(page), mixedRaw);
        } finally { await tab.context.close(); }
      }
    });

    await run('preview identity cannot change actual costs', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      const tab = await launch(), { page } = tab;
      try {
        const result = await page.evaluate(async raw => {
          const p = SCStock.handoff.previewBackup(raw), changed = JSON.parse(raw);
          changed.items.find(item => item.kind === 'independent_research').report.entry_fees = '999.99';
          p.preview.raw = JSON.stringify(changed);
          return SCStock.handoff.restoreBackup(p.preview);
        }, mixedRaw);
        eq('preview identity: same count/kinds/dates cannot substitute actual fee bytes', [result.ok, await stored(page), await writes(page)], [false, null, 0]);
        eq('preview identity: rejected substitution keeps destination readable', await page.evaluate(() => SCStock.handoff.status().available), true);
      } finally { await tab.context.close(); }
    });

    await run('no publication recovery access', async () => {
      if (!mixedRaw) throw Error('Mixed module-produced backup unavailable');
      for (const seed of [mixedRaw, null]) {
        const tab = await launch({ seed, noPublication: true, width: 390, theme: 'light' }), { page } = tab;
        try {
          const start = tab.requests.length;
          eq('no publication: public authority is absent', await page.evaluate(() => [SCStock.data, SCStock.model, SCStock.observations.facts().recordHash]), [null, null, null]);
          eq('no publication: recovery disclosure remains reachable', await page.locator('[data-handoff-backup]').isVisible(), true);
          if (seed) eq('no publication: healthy saved backup exports exactly', (await download(page)).raw.toString('utf8'), seed);
          else { await chooseFile(page, mixedRaw); await confirm(page); eq('no publication: explicit empty-only restore needs no new source fetch', await stored(page), mixedRaw); }
          eq('no publication: restored private planned and independent cannot gain copy authority', await page.evaluate(() => SCStock.handoff.list().map(item => SCStock.handoff.copy(item.id).ok)), [false, false]);
          eq('no publication: original unknown exit facts remain unknown', (await saved(page)).find(item => item.kind === 'independent_research').report.exited_at, null);
          await capture(page, 'private-backup-no-publication-' + (seed ? 'saved' : 'restore'));
          await privateOnly(tab, start, 'no publication');
        } finally { await tab.context.close(); }
      }
    });
  } finally { await rm(scratch, { recursive: true, force: true }); }
}
