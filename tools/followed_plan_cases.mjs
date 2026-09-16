import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NOW = '2026-09-10T22:31:00Z';

export async function checkFollowedPlan({browser, base, data, open, check, eq, shotsDir}) {
  console.log('-- followed published plan');
  const ticket = data.bursts.find(b => data.trades.includes(b.ticker));
  const app = await open(browser, base, '/tests/fixtures/page/full.json', NOW, 1280,
    {hash:'#/explore/bursts/' + ticket.ticker});
  const {page} = app;
  const count = await page.locator('#detail [data-select-plan]').count();
  eq('ticket offers explicit plan selection independently of saving', count, 1);
  if (!count) {await app.context.close(); return;}
  const read = () => page.evaluate(() => SCStock.follow.list());
  const route = async hash => {await page.evaluate(h => SCStock.navigate(h), hash); await page.waitForTimeout(100);};
  const render = async record => {await page.evaluate(r => SCStock.render(r, new Date('2026-09-11T22:31:00Z')), record); await page.waitForTimeout(180);};
  const next = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/next.json'), 'utf8'));
  const publicBefore = await page.evaluate(() => JSON.stringify(SCStock.data));
  await page.locator('#detail [data-select-plan]').focus(); await page.keyboard.press('Enter');
  await page.waitForFunction(() => SCStock.follow.list().some(i => i.plan_selection));
  const original = (await read())[0], id = original.id;
  const lean = structuredClone(original); lean.evidence = null; lean.evidence_dropped = true; delete lean.plan_selection;
  console.log('  saved setup characters: ' + JSON.stringify({withChart:JSON.stringify({version:4,items:[original]}).length, withoutChart:JSON.stringify({version:4,items:[lean]}).length}));
  eq('selection saves exactly one original', (await read()).length, 1);
  eq('selection keeps exact order and whole-plan identity', original.snapshot.published_plan,
    {order_json:ticket.plan.order_json, horizon_end:ticket.plan.exit_schedule.at(-1).date});
  eq('selection retains original applicable session', original.snapshot.timing.applicable_session, data.run.timing.applicable_session);
  eq('selection pins published receipt', original.plan_selection.reference, ticket.plan.evidence_ref);
  const competing = structuredClone(original); delete competing.id;
  competing.snapshot.evidence_ref.id = '0'.repeat(64);
  const collision = await page.evaluate(item => SCStock.follow.commit('selectPlan', item, false), competing);
  check('another publication cannot inherit this selection', !collision.ok && /different publication/.test(collision.error));
  check('selection records a browser-local time', Number.isFinite(Date.parse(original.plan_selection.selected_at)), original.plan_selection);
  eq('no execution quantity or purchase price required', [original.reference_shares, original.purchase_price, original.annotation], [null, undefined, undefined]);
  eq('selection does not change the public record or population', await page.evaluate(() => JSON.stringify(SCStock.data)), publicBefore);
  eq('selected control announces state', await page.getAttribute('#detail [data-select-plan]', 'aria-pressed'), 'true');
  await page.reload(); await page.waitForFunction(() => document.documentElement.dataset.ssRendered);
  eq('reload keeps original plan and selection time', (await read())[0].plan_selection, original.plan_selection);
  await page.evaluate(async id => {await SCStock.follow.commit('setShares', id, 7); await SCStock.follow.commit('setAnnotation', id, 'amount', '123.45');}, id);
  await render(next); await route('#/setups');
  check('real pipeline sequel provides exactly matched stopped model', /Model plan: STOPPED/.test(await page.locator('#following').innerText()));
  const observed = (await read())[0];
  eq('model observation carries exact evidence id', observed.model_observation.row.evidence_ref.id, original.plan_selection.reference.id);
  eq('automatic observation preserves original evidence and snapshot', [observed.snapshot, observed.evidence], [original.snapshot, original.evidence]);
  eq('reference amount and shares remain personal references', [observed.annotation.reference_amount.minor_units, observed.reference_shares], [12345, 7]);
  eq('model result ingestion leaves public JSON unchanged', await page.evaluate(() => JSON.stringify(SCStock.data)), JSON.stringify(next));
  check('observed movement remains distinct from execution', /recorded closes, not your result/.test(await page.locator('#following').innerText()));
  const statuses = ['hold','not_filled','uncertain','expired','unmeasured'];
  for (const status of statuses) {
    const variant = structuredClone(next), row = variant.open_plans.find(p => p.ticker === ticket.ticker && p.picked === data.run.session);
    row.status = status; variant.run.published_at = '2026-09-11T23:00:0' + statuses.indexOf(status) + 'Z';
    await render(variant); await route('#/setups');
    check('public model state remains explicit: ' + status, (await page.locator('#following [data-personal-model-state]').innerText()).includes(status.replace('_',' ').toUpperCase()));
    check('state is never personal execution: ' + status, !/you (bought|sold|were stopped)|your (profit|loss)/i.test(await page.locator('#following').innerText()));
  }
  const last = (await read())[0].model_observation;
  await render(next);
  eq('older same-session publication cannot replace newer model evidence', (await read())[0].model_observation, last);
  await render(data); await route('#/setups');
  eq('older record cannot replace newer model evidence', (await read())[0].model_observation, last);
  check('older page names newer cached outcome', /newer than this loaded record/.test(await page.locator('#following [data-plan-coverage]').innerText()));
  const mismatch = structuredClone(next);
  mismatch.run.published_at = '2026-09-11T23:59:00Z';
  mismatch.open_plans.find(p => p.ticker === ticket.ticker).evidence_ref.id = '0'.repeat(64);
  await render(mismatch);
  eq('same ticker and date with different evidence cannot overwrite outcome', (await read())[0].model_observation, last);
  const later = structuredClone(next); later.open_plans = []; later.run.session = '2026-10-20';
  await render(later); await route('#/setups');
  check('missing current model observation keeps its dated last evidence', /No newer exact model observation/.test(await page.locator('#following [data-plan-coverage]').innerText()));
  await route('#/followed/' + encodeURIComponent(id));
  check('saved detail explains public observation horizon', /public observation window has ended/.test(await page.locator('#saved').innerText()));
  await page.locator('#saved [data-select-plan]').click(); await page.waitForTimeout(100);
  eq('clearing selection retains the saved original', [(await read()).length, (await read())[0].plan_selection], [1, undefined]);
  await page.locator('#saved [data-select-plan]').click(); await page.waitForTimeout(100);
  check('missing terminal outcome stays unknown after horizon', /window ended/.test(await page.locator('#saved [data-plan-coverage]').innerText()));
  await page.locator('#saved-close').click();

  // Shared origin and Web Locks: the other tab can annotate without losing
  // this tab's plan selection; a stale edit cannot resurrect a removed item.
  const tab = await app.context.newPage();
  await tab.addInitScript(() => {window.SCStock = {dataUrl:'/tests/fixtures/page/full.json', now:'2026-09-10T22:31:00Z'};});
  await tab.goto(base + '/docs/index.html'); await tab.waitForFunction(() => document.documentElement.dataset.ssRendered);
  await Promise.all([
    page.evaluate(id => SCStock.follow.commit('setShares', id, 8), id),
    tab.evaluate(id => SCStock.follow.commit('setAnnotation', id, 'amount', '88.88'), id)
  ]);
  const shared = (await read())[0];
  eq('two-tab references and plan selection all survive', [shared.reference_shares, shared.annotation.reference_amount.minor_units, !!shared.plan_selection], [8, 8888, true]);
  await page.evaluate(id => SCStock.follow.commit('remove', id), id);
  const refusal = await tab.evaluate(item => SCStock.follow.commit('selectPlan', item, true), shared);
  check('stale plan selection refuses a removed setup', !refusal.ok && /removed/.test(refusal.error));
  eq('removed setup is not resurrected', (await read()).length, 0);
  await tab.close();

  // A pre-feature note keeps its meaning and is never silently upgraded.
  const legacy = structuredClone(original); delete legacy.plan_selection; delete legacy.snapshot.published_plan;
  delete legacy.snapshot.evidence_ref.plan_sha256; delete legacy.snapshot.evidence_ref.pick_sha256;
  legacy.annotation = {taken:true, taken_marked_at:'2026-09-11T12:00:00Z', reference_amount:{currency:'USD', minor_units:9911}};
  legacy.reference_shares = 9;
  await page.evaluate(item => localStorage.setItem(SCStock.follow.DEMO_KEY, JSON.stringify({version:3, items:[item]})), legacy);
  await render(data); await route('#/followed/' + encodeURIComponent(id));
  eq('legacy take note never becomes plan selection', (await read())[0].plan_selection, undefined);
  check('legacy note is labelled and preserved', /Legacy note: I took this setup/.test(await page.locator('#saved').innerText()));
  eq('legacy store migrates with original references intact', await page.evaluate(() => {const v=JSON.parse(localStorage.getItem(SCStock.follow.DEMO_KEY));return [v.version, v.items[0].reference_shares, v.items[0].annotation.reference_amount.minor_units];}), [4,9,9911]);
  await page.locator('#saved [data-select-plan]').click(); await page.waitForTimeout(100);
  check('legacy selection discloses incomplete identity', /Legacy plan identity is incomplete/.test(await page.locator('#saved [data-plan-coverage]').innerText()));
  eq('legacy note unchanged by explicit selection', (await read())[0].annotation, legacy.annotation);
  await page.locator('#saved-close').click();

  // Restore a receipt-enabled selection for layout acceptance.
  await page.evaluate(item => localStorage.setItem(SCStock.follow.DEMO_KEY, JSON.stringify({version:4,items:[item]})), original);
  await render(next); await route('#/setups');
  for (const width of [1280,390,320]) for (const theme of ['dark','light']) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
    await page.waitForTimeout(90);
    check('followed plan fits ' + width + ' ' + theme, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (shotsDir) await page.screenshot({path:path.join(shotsDir, 'followed-plan-' + width + '-' + theme + '.png'),fullPage:true});
  }
  await route('#/followed/' + encodeURIComponent(id));
  eq('saved selection control is keyboard accessible', await page.locator('#saved [data-select-plan]').getAttribute('type'), 'button');
  await page.keyboard.press('Escape');
  eq('Escape closes saved detail', await page.locator('#saved').evaluate(el => el.open), false);
  eq('followed-plan page errors', app.errors, []);
  await app.context.close();

  const savedOnly = await open(browser, base, '/tests/fixtures/page/full.json', NOW, 1280, {hash:'#/explore/bursts/'+ticket.ticker});
  await savedOnly.page.locator('#detail [data-follow-action="add"]').click();
  await savedOnly.page.waitForFunction(() => SCStock.follow.list().length === 1);
  await savedOnly.page.evaluate(r => {SCStock.render(r,new Date('2026-09-11T22:31:00Z'));SCStock.navigate('#/followed/'+encodeURIComponent(SCStock.follow.list()[0].id));}, next);
  await savedOnly.page.waitForTimeout(180);
  check('saved native plan without personal selection identifies its exact public match', /matches the frozen evidence and plan identities/.test(await savedOnly.page.locator('#saved [data-model-update]').innerText()));
  await savedOnly.page.evaluate(r => SCStock.render(r,new Date('2026-09-11T22:31:00Z')), mismatch);
  await savedOnly.page.waitForTimeout(180);
  eq('saved native plan cannot inherit a different same-session publication', await savedOnly.page.locator('#saved [data-model-update]').getAttribute('data-model-update'), 'apart');
  check('different plan identity is disclosed', /different or missing plan identity/.test(await savedOnly.page.locator('#saved [data-model-update]').innerText()));
  await savedOnly.context.close();

  const failing = await open(browser, base, '/tests/fixtures/page/full.json', NOW, 390, {hash:'#/explore/bursts/'+ticket.ticker});
  await failing.page.evaluate(() => {const set = Storage.prototype.setItem; Storage.prototype.setItem = function(k,v){if(k === SCStock.follow.DEMO_KEY)throw Error('quota'); return set.call(this,k,v);};});
  await failing.page.locator('#detail [data-select-plan]').click();
  await failing.page.waitForFunction(() => /Could not confirm|Storage/.test(document.querySelector('#detail .ss-plan-selection').textContent));
  check('storage failure discloses refusal', /Could not confirm|Storage/.test(await failing.page.locator('#detail .ss-plan-selection').innerText()));
  eq('failed selection never claims saved state', await failing.page.evaluate(() => SCStock.follow.list().length), 0);
  await failing.context.close();
}
