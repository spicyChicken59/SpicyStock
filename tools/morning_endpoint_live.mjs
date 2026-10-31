/* A live read of the deployed morning receipt endpoint from the site's own origin.

   Not part of any CI gate: it reads the real service, on the real clock. The page is
   served from this checkout under https://spicychicken59.github.io/SpicyStock/, so the
   browser sends the origin the service's CORS rule names; only the endpoint named by
   the committed `spicystock-morning-endpoint` tag is let through to the network, and
   every other off-origin request is refused. It prints what the browser sent and was
   answered, and what the page made of it, and changes nothing anywhere.

   node tools/morning_endpoint_live.mjs [--shots <dir>] */
import { readFile, stat, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = path.resolve(import.meta.dirname, '..');
const SITE = 'https://spicychicken59.github.io/SpicyStock/';
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.gz': 'application/gzip' };
const shots = process.argv.includes('--shots') ? process.argv[process.argv.indexOf('--shots') + 1] : null;

async function loadChromium() {
  const tries = [() => import('playwright'),
    ...[...(process.env.NODE_PATH || '').split(':'), path.resolve(path.dirname(process.execPath), '..', 'lib', 'node_modules')]
      .filter(Boolean).map(root => () => import(pathToFileURL(path.join(root, 'playwright', 'index.js')).href))];
  for (const t of tries) { try { const m = await t(); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; } catch { /* next */ } }
  return null;
}

const shell = await readFile(path.join(ROOT, 'docs/index.html'), 'utf8');
const tag = shell.match(/<meta name="spicystock-morning-endpoint" content="([^"]*)">/);
if (!tag || !tag[1]) { console.log('the committed shell names no morning endpoint; nothing to read'); process.exit(2); }
const endpoint = tag[1];
const chromium = await loadChromium();
if (!chromium) { console.log('playwright is not installed'); process.exit(1); }
const browser = await chromium.launch();
const sent = [], answered = [], refused = [], errors = [];
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.href.startsWith(SITE)) {
      let file = path.join(ROOT, 'docs', decodeURIComponent(url.pathname.slice('/SpicyStock/'.length)));
      if (!file.startsWith(path.join(ROOT, 'docs'))) return route.fulfill({ status: 404, body: '' });
      try { if ((await stat(file)).isDirectory()) file = path.join(file, 'index.html'); } catch { return route.fulfill({ status: 404, body: '' }); }
      try { return route.fulfill({ status: 200, contentType: MIME[path.extname(file)] || 'application/octet-stream', body: await readFile(file) }); }
      catch { return route.fulfill({ status: 404, body: '' }); }
    }
    if (url.href === endpoint) { sent.push(await route.request().allHeaders()); return route.continue(); }
    refused.push(url.origin + url.pathname);
    return route.abort();
  });
  const reply = page.waitForResponse(r => r.url() === endpoint, { timeout: 30000 }).catch(() => null);
  await page.goto(SITE, { waitUntil: 'load' });
  const r = await reply;
  // status and headers only: a routed response's body is not read back here
  if (r) answered.push({ status: r.status(), headers: await r.allHeaders() });
  await page.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'), null, { timeout: 30000 });
  await page.waitForFunction(() => window.SCStock && SCStock.observations && !['unbound', 'loading'].includes(SCStock.observations.facts().state), null, { timeout: 30000 }).catch(() => {});
  const facts = await page.evaluate(() => { const f = SCStock.observations.facts(); return { state: f.state, headline: f.headline, generated_at: f.generatedAt || null, fresh: f.fresh, publication_bound: f.canonicalHash || null }; });
  const said = await page.evaluate(() => { const n = document.querySelector('[data-morning-observations], #morning-observations, [data-observations]'); return n ? n.textContent.replace(/\s+/g, ' ').trim().slice(0, 300) : null; });
  if (shots) { await mkdir(shots, { recursive: true }); await page.screenshot({ path: path.join(shots, 'morning-endpoint-live.png'), fullPage: false }); }
  const keep = h => Object.fromEntries(Object.entries(h).filter(([k]) => ['origin', 'referer', 'cookie', 'authorization'].includes(k)));
  const show = h => Object.fromEntries(Object.entries(h).filter(([k]) => ['access-control-allow-origin', 'cache-control', 'vary', 'etag', 'content-type'].includes(k)));
  console.log(JSON.stringify({ endpoint, at: new Date().toISOString(), requests: sent.map(keep), responses: answered.map(a => ({ status: a.status, headers: show(a.headers) })),
    page: { ...facts, said }, refused_off_origin: [...new Set(refused)], page_errors: errors }, null, 2));
} finally { await browser.close(); }
