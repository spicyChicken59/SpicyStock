// Verify the Home-inspired signal map against recorded and clearly labeled fixture data.
// NODE_PATH=/path/to/node_modules node tools/signal_map_smoke.mjs [--shots /tmp/proof]
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let chromium;
for (const path of (process.env.NODE_PATH || '').split(':').filter(Boolean)) {
  try { ({ chromium } = await import(pathToFileURL(join(path, 'playwright/index.mjs')))); break; } catch {}
}
if (!chromium) ({ chromium } = await import('playwright'));
const fixture = JSON.parse(await readFile(join(repo, 'tests/fixtures/data.json'), 'utf8'));
const recorded = JSON.parse(await readFile(join(repo, 'docs/data.json'), 'utf8'));
const files = { '.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png' };
const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (path === '/data.json') { res.writeHead(200, {'Content-Type':'application/json'}); res.end(JSON.stringify(fixture)); return; }
    const file = resolve(repo, 'docs', '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(join(repo, 'docs') + '/')) throw new Error('outside docs');
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': files[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.fulfill({status:200,body:''}));
const shotArg = process.argv.indexOf('--shots');
const shots = shotArg < 0 ? null : resolve(process.argv[shotArg + 1]);
if (shots) await mkdir(shots, {recursive:true});
let scenarios = 0;
try {
  for (const width of [1280, 390, 320]) {
    for (const theme of ['light', 'dark']) {
      await page.setViewportSize({width,height:900});
      await page.goto(origin);
      if (!await page.locator('#research-report').evaluate(node => node.open)) await page.locator('#research-toggle').click();
      await page.waitForSelector('.signal-card');
      await page.click(`.sc-theme-toggle button[data-theme="${theme}"]`);
      assert.equal(await page.locator('.signal-card').count(), fixture.candidates.length);
      assert.equal(await page.locator('.signal-point').count(), fixture.candidates.length);
      assert.equal(await page.locator('.signal-provenance.is-fallback').count(), fixture.candidates.filter(c => c.provenance?.source !== 'claude').length);
      const last = fixture.candidates.length - 1;
      await page.locator('.signal-point').nth(last).focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('.signal-card.is-selected').getAttribute('id'), `signal-candidate-${last}`);
      assert.match(await page.locator('.signal-selection').textContent(), new RegExp(fixture.candidates[last].ticker));
      await page.locator('.signal-card-select').first().click();
      assert.equal(await page.locator('.signal-point.is-selected').getAttribute('data-signal-index'), '0');
      await page.locator('.signal-record-link').first().click();
      assert.equal(await page.evaluate(() => document.activeElement.id), 'signal-record-0');
      assert.match(await page.locator('#signal-record-0').textContent(), new RegExp(fixture.candidates[0].ticker));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${width}/${theme}: page overflow`);
      assert.equal(await page.locator('.signal-card-select').first().evaluate(n => n.getBoundingClientRect().height >= 44), true);
      if (shots && width !== 320) {
        await page.locator('#signal-workspace').evaluate(n => n.scrollIntoView({block:'start'}));
        await page.screenshot({path:join(shots, `signal-fixture-${width}-${theme}.png`)});
      }
      scenarios++;
    }
  }
  await page.evaluate(d => window.SCStockSignals.render(d), recorded);
  assert.equal(await page.locator('.signal-card').count(), recorded.candidates.length);
  if (!recorded.candidates.length) {
    assert.equal(await page.locator('.signal-point').count(), 0);
    assert.match(await page.locator('.signal-map-empty').textContent(), /No scored signals/);
  }
  const incomplete = structuredClone(fixture);
  incomplete.candidates[0].gain_pct = null;
  incomplete.candidates[1].volume_ratio = '4.2';
  incomplete.candidates[2].volume_ratio = -1;
  delete incomplete.candidates[3].provenance;
  incomplete.candidates[4].provenance.chart_seen = false;
  incomplete.candidates[5].ticker = '<img src=x onerror=alert(1)>';
  await page.evaluate(d => window.SCStockSignals.render(d), incomplete);
  assert.equal(await page.locator('.signal-point').count(), fixture.candidates.length - 3);
  assert.equal(await page.locator('.signal-card').count(), fixture.candidates.length);
  assert.match(await page.locator('#signal-candidate-0').textContent(), /Not recorded/);
  assert.match(await page.locator('#signal-candidate-3').textContent(), /Source not recorded/);
  assert.match(await page.locator('#signal-candidate-4').textContent(), /Scored without the chart/);
  assert.equal(await page.locator('#signal-candidate-5 img').count(), 0);
  assert.equal(await page.locator('#signal-candidate-5 .signal-card-select').textContent(), incomplete.candidates[5].ticker);
  await page.locator('.signal-card-select').first().click();
  assert.match(await page.locator('.signal-selection').textContent(), /incomplete/);
  const failed = {run:{date:'2026-09-08',status:'failed',errors:[{message:'no feed response'}]},candidates:[]};
  await page.evaluate(d => window.SCStockSignals.render(d), failed);
  assert.equal(await page.locator('.signal-point').count(), 0);
  assert.doesNotMatch(await page.locator('#signal-content').textContent(), /quiet session|no bursts/i);
  const malformed = structuredClone(fixture);
  malformed.candidates.at(-1).lynch_detail = 'not a checklist';
  await page.route(origin + '/data.json', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(malformed)}));
  await page.goto(origin);
      if (!await page.locator('#research-report').evaluate(node => node.open)) await page.locator('#research-toggle').click();
  await page.waitForFunction(() => document.getElementById('snapshot-status').textContent.includes('Snapshot unavailable'));
  assert.equal(await page.locator('#signal-workspace').isVisible(), false, 'A failed first render must not leave partially rendered candidate evidence visible');
  assert.deepEqual(errors, []);
  console.log(`Signal map: ${scenarios} viewport/theme scenarios, keyboard selection, record links, provenance, missing values, hostile text and failed/empty states passed.`);
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
