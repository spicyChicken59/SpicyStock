/* Private model controls over the committed run_evening-produced cash fixture.
   No HTTP, provider calls, fabricated production record or browser UI stubs.
   The page's actual morning facts/cash arithmetic are loaded; availability and
   observation authority are explicit injected boundaries, covered again in
   the real browser suite. SCSTOCK_HANDOFF permits isolated source mutations. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { createHash } from 'node:crypto';

const ROOT = path.resolve(import.meta.dirname, '..');
const raw = await readFile(path.join(ROOT, 'tests/fixtures/cash-preview/publication.json'), 'utf8');
const HASH = createHash('sha256').update(raw).digest('hex');
const scripts = await Promise.all(['docs/app-cash-preview.js', 'docs/app-morning.js', process.env.SCSTOCK_HANDOFF || 'docs/app-handoff.js'].map(file => readFile(path.resolve(ROOT, file), 'utf8')));
const NOW = '2026-09-11T13:35:00.000Z';
const plain = value => JSON.parse(JSON.stringify(value));
const reportFields = patch => ({ submitted_quantity: '', submitted_at: '', filled_quantity: '', average_price: '', filled_at: '', cancelled_quantity: '', cancelled_at: '', exited_quantity: '', exited_at: '', protected_quantity: '', protection_confirmed_at: '', ...patch });

function environment(options = {}) {
  const state = { now: NOW, hash: HASH, restriction: null, readFails: false, writeFails: false, badReadback: false, blockLock: null, ...options };
  const store = options.store || new Map(), events = new Map();
  const data = JSON.parse(raw);
  const makeCandidate = (row, stage) => ({ ticker: row.ticker, stage, status: row.plan?.eligible ? 'ticket' : 'withheld', plan: row.plan, row });
  const api = { data, avail: { offered: true, reason: '', pub: { state: 'fresh' }, timing: {}, phase: 'open' },
    model: { stages: { bursts: data.trades.map(row => makeCandidate(row, 'bursts')), 'setting-up': data.watchlist.top.map(row => makeCandidate(row, 'setting-up')) } },
    observations: { facts: () => ({ canonicalHash: state.hash }), refusal: () => state.restriction } };
  api.reclock = () => { api.avail.offered = Date.parse(state.now) < Date.parse(data.run.timing.cutoff_at); api.avail.reason = api.avail.offered ? '' : 'Entry window ended.'; };
  let queue = Promise.resolve();
  const locks = { request: async (key, fn) => {
    if (state.blockLock) { const waiting = state.blockLock; state.blockLock = null; await waiting; }
    const result = queue.then(fn); queue = result.catch(() => {}); return result;
  } };
  const storage = { getItem: key => { if (state.readFails) throw Error('read blocked'); const got = store.get(key) ?? null; return state.badReadback && got !== null ? got + ' ' : got; },
    setItem: (key, value) => { if (state.writeFails) throw Error('quota'); store.set(key, value); }, removeItem: key => store.delete(key) };
  const window = { SCStock: api, localStorage: storage, navigator: state.noLocks ? {} : { locks }, TextEncoder, addEventListener: (type, fn) => events.set(type, fn) };
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [state.now])); } static now() { return Date.parse(state.now); } }
  const context = vm.createContext({ window, Date: Clock });
  scripts.forEach(script => vm.runInContext(script, context));
  const handoff = api.handoff;
  return { api, handoff, state, store, events,
    prepare: patch => handoff.prepare({ key: 'setting-up:COIL', cash: '2000', fees: '1', quantity: '2', expectedPublication: HASH, expectedRevision: null, ...patch }) };
}

test('real producer draft keeps published four and personally reads back two without inferred execution', async () => {
  const env = environment(), original = JSON.stringify(env.api.data);
  const result = await env.prepare(); assert.equal(result.ok, true, result.error);
  const item = plain(result.item), summary = plain(env.handoff.summary(result.item));
  assert.equal(item.publication.sha256, HASH);
  assert.equal(item.plan.order.quantity, 4); assert.equal(item.plan.order.then.quantity, 4);
  assert.deepEqual(item.draft, { quantity: 2, cash_cents: 200000, fee_cents: 100 });
  assert.equal(summary.calculation.commitmentCents, 22444); assert.equal(summary.calculation.riskCents, 444);
  assert.equal(summary.reported_held_quantity, null); assert.equal(summary.unfilled_quantity, null); assert.equal(summary.protection, 'unknown');
  assert.ok(Object.values(item.report).every(value => value === null));
  const copy = env.handoff.copy(item.id); assert.equal(copy.ok, true);
  assert.match(copy.text, /BUY 2 COIL/); assert.match(copy.text, /protective SELL 2 COIL/); assert.match(copy.text, /Published quantity: 4/);
  assert.match(copy.text, /places no order or protective stop/);
  assert.equal(JSON.stringify(env.api.data), original); assert.equal(env.handoff.find(item.id).revision, 1);
  assert.equal(env.store.size, 1); assert.equal(env.store.has('spicystock:following:v1'), false);
});

test('one of two filled means one reported held, one unfilled, cancellation and protection still unknown', async () => {
  const env = environment(), { item } = await env.prepare();
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', average_price: '111.234500', filled_at: '2026-09-11T08:34:30-05:00' }), item.revision);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.state, 'reported_partial_fill'); assert.equal(summary.reported_held_quantity, 1); assert.equal(summary.unfilled_quantity, 1);
  assert.equal(summary.uncancelled_quantity, null); assert.equal(summary.protection, 'unknown');
  assert.equal(result.item.report.average_price, '111.2345'); assert.equal(result.item.report.filled_at, '2026-09-11T13:34:30.000Z');
  assert.equal(env.handoff.copy(item.id).ok, false); // readback is retained, never a second entry instruction
  assert.match(env.handoff.readback(result.item), /BUY 2 COIL/);
});

test('explicit zero fills differ from unknown, with no implied price or broker protection', async () => {
  const env = environment(), { item } = await env.prepare();
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '0', exited_quantity: '0', cancelled_quantity: '0' }), 1);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.reported_held_quantity, 0); assert.equal(summary.unfilled_quantity, 2); assert.equal(summary.uncancelled_quantity, 2);
  assert.equal(result.item.report.average_price, null); assert.equal(summary.protection, 'unknown');
});

test('unknown exits never mean still held; explicit exits reconcile holdings and stale protection after expiry', async () => {
  const env = environment(), { item } = await env.prepare();
  let result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', protected_quantity: '1' }), 1);
  assert.equal(result.ok, true, result.error);
  let summary = env.handoff.summary(result.item);
  assert.equal(summary.filled_quantity, 1); assert.equal(summary.exited_quantity, null); assert.equal(summary.reported_held_quantity, null); assert.equal(summary.protection, 'unknown');
  env.state.now = '2026-09-11T16:00:00Z'; env.state.restriction = 'Known halt';
  result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', filled_at: NOW, cancelled_quantity: '1', exited_quantity: '1', exited_at: '2026-09-11T15:00:00Z', protected_quantity: '1' }), result.item.revision);
  assert.equal(result.ok, true, result.error);
  summary = env.handoff.summary(result.item);
  assert.equal(summary.filled_quantity, 1); assert.equal(summary.exited_quantity, 1); assert.equal(summary.reported_held_quantity, 0); assert.equal(summary.state, 'reported_closed');
  assert.equal(summary.protection, 'over'); assert.match(summary.warnings.join(' '), /remaining holdings/);
  result = await env.handoff.report(item.id, { ...result.item.report, protected_quantity: '0', protection_confirmed_at: env.state.now }, result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).protection, 'matched');
  assert.equal(result.item.plan.order.quantity, 4); assert.equal(env.handoff.copy(item.id).ok, false);
});

test('exit conservation and chronology reject impossible reports without confusing partial-entry timing', async () => {
  const env = environment(), { item } = await env.prepare();
  const base = { submitted_quantity: '2', submitted_at: '2026-09-11T13:30:00Z', filled_quantity: '2', filled_at: '2026-09-11T13:34:00Z' };
  for (const patch of [
    { exited_quantity: '3' }, { filled_quantity: '', filled_at: '', exited_quantity: '1' },
    { exited_quantity: '0', exited_at: NOW }, { exited_quantity: '1', exited_at: '2026-09-11T13:29:00Z' },
    { exited_quantity: '2', exited_at: '2026-09-11T13:33:00Z' }, { exited_quantity: '1', exited_at: '2026-09-11T13:35:06Z' }
  ]) assert.equal((await env.handoff.report(item.id, reportFields({ ...base, ...patch }), 1)).ok, false, JSON.stringify(patch));
  // One earlier fill may have exited before the latest partial entry filled.
  const result = await env.handoff.report(item.id, reportFields({ ...base, exited_quantity: '1', exited_at: '2026-09-11T13:33:00Z' }), 1);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1);
});

test('protective mismatch is a retained fact, including overprotection, and corrections reconcile it', async () => {
  const env = environment(), { item } = await env.prepare();
  let latest = item;
  for (const [quantity, expected] of [['0', 'under'], ['2', 'over'], ['1', 'matched']]) {
    const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', protected_quantity: quantity, protection_confirmed_at: NOW }), latest.revision);
    assert.equal(result.ok, true, result.error); latest = result.item;
    assert.equal(latest.report.protected_quantity, Number(quantity));
    const summary = env.handoff.summary(latest); assert.equal(summary.protection, expected);
    assert.equal(summary.warnings.some(value => /protective quantity/.test(value)), expected !== 'matched');
  }
  assert.equal(latest.revision, 4); assert.equal(latest.plan.order.quantity, 4);
});

test('reported quantities, prices and times outside the plan remain factual deviations after expiry', async () => {
  const env = environment(), { item } = await env.prepare();
  env.state.now = '2026-09-11T15:00:00.000Z'; env.state.restriction = 'Source-backed halt'; env.state.hash = 'c'.repeat(64);
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '5', submitted_at: '2026-09-11T14:00:00Z', filled_quantity: '3', exited_quantity: '0', average_price: '115', filled_at: '2026-09-11T14:01:00Z' }), 1);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.reported_held_quantity, 3); assert.equal(summary.unfilled_quantity, 2); assert.equal(summary.warnings.length, 3);
  assert.equal(env.handoff.copy(item.id).ok, false);
  const reread = environment({ store: env.store, now: env.state.now });
  assert.equal(reread.handoff.find(item.id).report.filled_quantity, 3);
  assert.equal(reread.handoff.find(item.id).plan.order.quantity, 4);
});

test('cumulative fill and cancellation conservation rejects impossible totals without overwriting', async () => {
  const env = environment(), { item } = await env.prepare();
  const before = env.store.get(env.handoff.KEY);
  for (const [submitted, filled, cancelled] of [['2', '3', ''], ['2', '1', '2'], ['2', '', '3'], ['', '1', ''], ['', '', '1']]) {
    const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: submitted, filled_quantity: filled, cancelled_quantity: cancelled }), 1);
    assert.equal(result.ok, false, [submitted, filled, cancelled].join('/')); assert.equal(env.store.get(env.handoff.KEY), before);
  }
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', cancelled_quantity: '1', cancelled_at: NOW }), 1);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).uncancelled_quantity, 0);
  assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1);
});

test('numeric and clock errors reject only malformed reports, preserving positive out-of-plan facts', async () => {
  const env = environment(), { item } = await env.prepare();
  const base = { submitted_quantity: '2', submitted_at: '2026-09-11T13:33:00Z', filled_quantity: '1', average_price: '111.2', filled_at: '2026-09-11T13:34:00Z' };
  for (const patch of [
    { filled_quantity: '1.5' }, { filled_quantity: '-1' }, { submitted_quantity: '1000001' }, { average_price: '0' }, { average_price: 'NaN' }, { average_price: '1e2' }, { average_price: '111.1234567' },
    { filled_at: '2026-09-11T13:34:00' }, { filled_at: '2026-02-30T13:34:00Z' }, { filled_at: '2026-09-11T25:00:00Z' }, { filled_at: '2026-09-11T13:35:06Z' },
    { filled_at: '2026-09-11T13:32:59Z' }, { cancelled_quantity: '1', cancelled_at: '2026-09-11T13:33:59Z' }, { filled_quantity: '0' }, { submitted_quantity: '0', filled_quantity: '', average_price: '', filled_at: '' }
  ]) {
    const result = await env.handoff.report(item.id, reportFields({ ...base, ...patch }), 1);
    assert.equal(result.ok, false, JSON.stringify(patch)); assert.equal(env.handoff.find(item.id).revision, 1);
  }
  const valid = await env.handoff.report(item.id, reportFields({ ...base, average_price: '99.000001' }), 1);
  assert.equal(valid.ok, true, valid.error); assert.equal(valid.item.report.average_price, '99.000001');
});

test('draft cap, cash and explicit fees remain separate from manually reported actual quantities', async () => {
  for (const patch of [{ quantity: '5' }, { cash: '224.43' }, { fees: '' }, { cash: '' }, { quantity: '0' }, { quantity: '1.2' }]) {
    const env = environment(), result = await env.prepare(patch); assert.equal(result.ok, false, JSON.stringify(patch)); assert.equal(env.store.size, 0);
  }
  const env = environment(), result = await env.prepare({ cash: '224.44' });
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).calculation.remainingCents, 0);
});

test('new preparation and detached copy recheck expiry, events, exact publication and plan identity', async () => {
  const controls = [
    ['expiry', env => { env.state.now = '2026-09-11T14:00:00Z'; }],
    ['halt', env => { env.state.restriction = 'Known active halt'; }],
    ['corporate', env => { env.state.restriction = 'Known merger exclusion'; }],
    ['binding pending', env => { env.state.hash = null; }],
    ['new publication', env => { env.state.hash = 'b'.repeat(64); }],
    ['withheld', env => { env.api.model.stages['setting-up'][0].status = 'withheld'; }],
    ['account mismatch', env => { env.api.data.account.equity = 10000; }],
    ['practice', env => { env.api.data.fixture = { label: 'explicit refusal control' }; }],
    ['order mismatch', env => { env.api.model.stages['setting-up'][0].plan.order_json.then.quantity = 3; }],
    ['level mismatch', env => { env.api.model.stages['setting-up'][0].plan.stop += .01; }],
    ['reference mismatch', env => { env.api.model.stages['setting-up'][0].plan.evidence_ref.plan_sha256 = 'c'.repeat(64); }]
  ];
  for (const [label, change] of controls) {
    const env = environment(), { item } = await env.prepare(); change(env);
    assert.equal(env.handoff.copy(item.id).ok, false, label + ' copy');
    const result = await env.prepare({ expectedRevision: 1 });
    // A different valid reference still creates a different-source draft only
    // if explicitly reviewed; an existing identity must never silently change.
    assert.equal(result.ok, false, label + ' preparation');
    assert.equal(env.handoff.find(item.id).draft.quantity, 2); assert.equal(env.handoff.find(item.id).plan.order.quantity, 4);
  }
});

test('guard is evaluated after waiting for the storage lock', async () => {
  let unlock; const waiting = new Promise(resolve => { unlock = resolve; });
  const env = environment({ blockLock: waiting });
  const pending = env.prepare(); env.state.now = '2026-09-11T14:00:00Z'; unlock();
  assert.equal((await pending).ok, false); assert.equal(env.store.size, 0);
});

test('optimistic revisions reject stale corrections and removed records without resurrection', async () => {
  const env = environment(), { item } = await env.prepare();
  const results = await Promise.all([
    env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1),
    env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2' }), 1)
  ]);
  assert.deepEqual(results.map(result => result.ok), [true, false]);
  assert.equal(env.handoff.find(item.id).report.filled_quantity, 1);
  assert.equal((await env.prepare({ expectedRevision: 2 })).ok, false);
  assert.equal((await env.handoff.remove(item.id, 1)).ok, false);
  assert.equal((await env.handoff.remove(item.id, 2)).ok, true);
  assert.equal((await env.handoff.report(item.id, reportFields(), 2)).ok, false);
  assert.equal(env.handoff.list().length, 0);
});

test('an explicit correction replaces cumulative totals and never adds a second fill', async () => {
  const env = environment(), { item } = await env.prepare();
  let result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2', average_price: '111' }), 1);
  result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', average_price: '110.8', cancelled_quantity: '1' }), result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1); assert.equal(result.item.report.average_price, '110.8');
  result = await env.handoff.report(item.id, reportFields(), result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, null);
  assert.ok(result.item.report_updated_at); assert.equal(result.item.plan.order.quantity, 4);
});

test('malformed or future stores remain untouched rather than losing reported holdings', async () => {
  const source = environment(), { item } = await source.prepare();
  await source.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  const valid = source.store.get(source.handoff.KEY);
  for (const alter of [() => '{', value => { value.version = 99; return JSON.stringify(value); }, value => { value.items[0].report.filled_quantity = 3; return JSON.stringify(value); }, value => { value.items.push(value.items[0]); return JSON.stringify(value); }, value => { value.items[0].plan.order.quantity = 1; return JSON.stringify(value); }]) {
    const raw = alter(JSON.parse(valid)), env = environment({ store: new Map([[source.handoff.KEY, raw]]) });
    assert.equal(env.handoff.status().available, false); assert.match(env.handoff.status().error, /left untouched/);
    assert.equal((await env.prepare()).ok, false); assert.equal(env.store.get(env.handoff.KEY), raw);
    assert.equal(env.handoff.recovery().prior, raw);
  }
});

test('write failures retain confirmed state and proposed recovery without claiming success', async () => {
  const env = environment(), { item } = await env.prepare(), before = env.store.get(env.handoff.KEY);
  env.state.writeFails = true;
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  assert.equal(result.ok, false); assert.equal(env.store.get(env.handoff.KEY), before);
  assert.equal(env.handoff.find(item.id).report.filled_quantity, null);
  assert.equal(JSON.parse(env.handoff.recovery().proposed).items[0].report.filled_quantity, 1);
  env.state.writeFails = false;
  assert.equal((await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1)).ok, true);
  assert.equal(env.handoff.recovery().proposed, null);
});

test('unavailable locks and storage fail readably; a normal reload preserves manual facts', async () => {
  const noLocks = environment({ noLocks: true }); assert.equal((await noLocks.prepare()).ok, false);
  const blocked = environment({ readFails: true }); assert.equal((await blocked.prepare()).ok, false); assert.equal(blocked.handoff.status().available, false);
  const env = environment(), { item } = await env.prepare();
  await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  const reload = environment({ store: env.store, noLocks: true });
  assert.equal(reload.handoff.find(item.id).report.filled_quantity, 1); assert.equal(reload.handoff.status().available, false);
});

test('explicit deletion alone removes reported records; notifications include cross-tab clears', async () => {
  const env = environment(); let changes = 0; env.handoff.onChange(() => { changes += 1; });
  const { item } = await env.prepare(); await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  assert.equal(changes, 2); env.events.get('storage')({ key: null }); assert.equal(changes, 3);
  assert.equal((await env.handoff.remove(item.id, 2)).ok, true); assert.equal(changes, 4); assert.equal(env.handoff.list().length, 0);
});

test('bounded private history refuses a new draft without silently evicting reported positions', async () => {
  const source = environment(), { item } = await source.prepare();
  const result = await source.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0' }), 1);
  // Explicit synthetic local-store controls, not new production publications.
  const items = Array.from({ length: source.handoff.MAX_ITEMS }, (_, index) => {
    const saved = plain(result.item); saved.publication.sha256 = index.toString(16).padStart(64, '0'); saved.id = saved.publication.sha256 + ':' + saved.plan.reference.id; return saved;
  });
  const raw = JSON.stringify({ version: 1, items }), env = environment({ store: new Map([[source.handoff.KEY, raw]]) });
  assert.equal(env.handoff.status().count, 100);
  const refused = await env.prepare(); assert.equal(refused.ok, false); assert.match(refused.error, /nothing was evicted/);
  assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.handoff.list().every(saved => env.handoff.summary(saved).reported_held_quantity === 1), true);
});
