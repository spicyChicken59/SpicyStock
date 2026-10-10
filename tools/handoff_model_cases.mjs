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
// Exact private-store bytes produced by the original v1 module at 067e792a
// over the committed cash publication, with explicitly synthetic manual facts.
// Kept inline because this runner owns its source controls, not public fixtures.
const LEGACY_RAW = "{\"version\":1,\"items\":[{\"version\":1,\"id\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399:4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"revision\":2,\"created_at\":\"2026-09-11T13:35:00.000Z\",\"updated_at\":\"2026-09-11T13:35:00.000Z\",\"publication\":{\"sha256\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399\",\"session\":\"2026-09-10\",\"published_at\":\"2026-09-10T22:30:00+00:00\",\"rules_version\":\"e87cdf5b1bbe\"},\"plan\":{\"reference\":{\"version\":1,\"id\":\"4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"context_sha256\":\"e7549e1ab149e27a3b207aa7a1bc801475732f4fb28af06994395d75e64d9cb4\",\"plan_sha256\":\"7ff63ac52be72aeb9b4e8d2b72516f692c57de3435f1b4c1153f51c479a4dab7\",\"pick_sha256\":\"52e839012fd40c9391900ff3bcb7465eaea23772e2a7c8e995d14ec8967ae98a\"},\"ticker\":\"COIL\",\"stage\":\"setting-up\",\"order\":{\"symbol\":\"COIL\",\"action\":\"buy\",\"quantity\":4,\"order_type\":\"stop_limit\",\"stop_price\":110.61,\"limit_price\":111.72,\"time_in_force\":\"day\",\"conditional\":\"one_triggers_the_other\",\"then\":{\"action\":\"sell\",\"quantity\":4,\"order_type\":\"stop\",\"stop_price\":109.5,\"time_in_force\":\"gtc\"}},\"timing\":{\"applicable_session\":\"2026-09-11\",\"opens_at\":\"2026-09-11T09:30:00-04:00\",\"cutoff_at\":\"2026-09-11T10:00:00-04:00\",\"closes_at\":\"2026-09-11T16:00:00-04:00\"},\"exit_schedule\":[{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry\",\"instruction\":\"buy only if it trades through $110.61 (limit $111.72) in the first 30 minutes; the sell stop at $109.50 is live from the fill; cancel the day order yourself if it has not filled by the end of the first 30 minutes.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"sell_half_8pct\",\"instruction\":\"if same or next day, the price reaches $119.46 (+8% from $110.61): sell half and move the stop to 25-50 cents under that day's high.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry_day_low\",\"instruction\":\"at the close of day 1: the stop rises to the entry day's low if that is above $109.50.\"},{\"day\":2,\"date\":\"2026-09-14\",\"key\":\"no_breakeven\",\"instruction\":\"if day 2 is green: do not move the stop to break-even before day 5 just because it is green.\"},{\"day\":3,\"date\":\"2026-09-15\",\"key\":\"day3\",\"instruction\":\"at the day 3 close: sell at least half at the close. If day 3 closes at or below $110.61: exit: no follow-through.\"},{\"day\":4,\"date\":\"2026-09-16\",\"key\":\"trail\",\"instruction\":\"raise the stop to each day's low (it never moves down); sell the rest into strength.\"},{\"day\":5,\"date\":\"2026-09-17\",\"key\":\"day5_exit\",\"instruction\":\"at the day 5 close: exit the remainder into strength.\"}]},\"draft\":{\"quantity\":2,\"cash_cents\":200000,\"fee_cents\":100},\"report\":{\"submitted_quantity\":2,\"submitted_at\":null,\"filled_quantity\":1,\"average_price\":\"111.23\",\"filled_at\":\"2026-09-11T13:34:00.000Z\",\"cancelled_quantity\":1,\"cancelled_at\":\"2026-09-11T13:35:00.000Z\",\"exited_quantity\":1,\"exited_at\":\"2026-09-11T13:35:00.000Z\",\"protected_quantity\":0,\"protection_confirmed_at\":null},\"report_updated_at\":\"2026-09-11T13:35:00.000Z\"}]}";

const plain = value => JSON.parse(JSON.stringify(value));
const reportFields = patch => ({ submitted_quantity: '', submitted_at: '', filled_quantity: '', average_price: '', filled_at: '', cancelled_quantity: '', cancelled_at: '', exited_quantity: '', exited_at: '', protected_quantity: '', protection_confirmed_at: '', average_exit_price: '', entry_fees: '', exit_fees: '', ...patch });

function environment(options = {}) {
  const state = { now: NOW, hash: HASH, restriction: null, readFails: false, writeFails: false, writes: 0, badReadback: false, blockLock: null, ...options };
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
    setItem: (key, value) => { state.writes++; if (state.writeFails) throw Error('quota'); store.set(key, value); }, removeItem: key => store.delete(key) };
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
  assert.equal(env.handoff.summary(result.item).state, 'reported_unknown_fill');
  assert.equal(env.handoff.copy(item.id).ok, false);
  assert.equal((await env.prepare({ expectedRevision: result.item.revision })).ok, false);
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
  const raw = JSON.stringify({ version: source.handoff.VERSION, items }), env = environment({ store: new Map([[source.handoff.KEY, raw]]) });
  assert.equal(env.handoff.status().count, 100);
  const refused = await env.prepare(); assert.equal(refused.ok, false); assert.match(refused.error, /nothing was evicted/);
  assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.handoff.list().every(saved => env.handoff.summary(saved).reported_held_quantity === 1), true);
});

const completedFields = patch => reportFields({ submitted_quantity: '2', filled_quantity: '2', average_price: '111.23', filled_at: '2026-09-11T13:34:00Z',
  cancelled_quantity: '0', exited_quantity: '2', exited_at: NOW, average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07', ...patch });

test('completed reported result uses actual quantities and fees, preserving the original draft buffer', async () => {
  const cases = [
    [{}, ['$7.54', '$0.12', '$7.42', 'gain', '7420000']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1' }, ['$3.77', '$0.12', '$3.65', 'gain', '3650000']],
    [{ average_exit_price: '109.50' }, ['-$3.46', '$0.12', '-$3.58', 'loss', '-3580000']],
    // Two actual partial entry fills averaged 111.25; two exits averaged114.50.
    [{ average_price: '111.25', average_exit_price: '114.5', entry_fees: '0.06', exit_fees: '0.08' }, ['$6.50', '$0.14', '$6.36', 'gain', '6360000']]
  ];
  for (const [patch, expected] of cases) {
    const env = environment(), before = JSON.stringify(env.api.data), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1);
    assert.equal(saved.ok, true, saved.error);
    const result = env.handoff.summary(saved.item).completed_result;
    assert.equal(result.state, 'complete'); assert.deepEqual(plain(result.reasons), []);
    assert.deepEqual([result.gross_display, result.fees_display, result.net_display, result.outcome, result.net_microusd], expected);
    assert.equal(saved.item.draft.fee_cents, 100); assert.equal(saved.item.plan.order.quantity, 4); assert.equal(saved.item.draft.quantity, 2);
    assert.equal(JSON.stringify(env.api.data), before); assert.equal(env.handoff.copy(item.id).ok, false);
  }
});

test('every missing result input remains unknown and exposes no numerical result', async () => {
  for (const field of ['filled_quantity', 'exited_quantity', 'submitted_quantity', 'cancelled_quantity', 'average_price', 'average_exit_price', 'entry_fees', 'exit_fees', 'filled_at', 'exited_at']) {
    const env = environment(), { item } = await env.prepare(), input = completedFields({ [field]: '' });
    // Remove dependent facts only when the existing report schema requires it.
    // The particular missing field must still be identified in result.missing.
    if (field === 'submitted_quantity' || field === 'filled_quantity') Object.assign(input, { filled_quantity: '', average_price: '', filled_at: '', cancelled_quantity: '', exited_quantity: '', exited_at: '', average_exit_price: '' });
    if (field === 'exited_quantity') Object.assign(input, { exited_at: '', average_exit_price: '' });
    const saved = await env.handoff.report(item.id, input, 1); assert.equal(saved.ok, true, field + ': ' + saved.error);
    const result = env.handoff.summary(saved.item).completed_result;
    assert.equal(result.state, 'incomplete', field); assert.ok(result.missing.includes(field), field);
    assert.ok(['gross_microusd', 'fees_microusd', 'net_microusd', 'gross_display', 'fees_display', 'net_display', 'outcome'].every(key => result[key] === null), field);
  }
});

test('partial exits and unreconciled entry remainders never invent a completed cost basis', async () => {
  for (const patch of [
    { exited_quantity: '1' }, { filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '0' },
    { filled_quantity: '0', exited_quantity: '0', cancelled_quantity: '2', average_price: '', filled_at: '', average_exit_price: '', exited_at: '' }
  ]) {
    const env = environment(), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, true, saved.error);
    const result = env.handoff.summary(saved.item).completed_result; assert.equal(result.state, 'incomplete'); assert.equal(result.net_microusd, null);
  }
  // buy1@100 -> sell1@110 -> buy1@120: latest avg entry110 cannot establish
  // the first sale's gross10. The aggregate report must not invent gross0.
  const env = environment(), { item } = await env.prepare();
  const saved = await env.handoff.report(item.id, completedFields({ average_price: '110', average_exit_price: '110', exited_quantity: '1' }), 1);
  assert.equal(saved.ok, true, saved.error);
  const result = env.handoff.summary(saved.item).completed_result;
  assert.equal(result.gross_display, null); assert.match(result.reasons.join(' '), /cost basis/);
});

test('explicit zero costs and exact sign survive cent rounding without false breakeven', async () => {
  const controls = [
    [{ average_exit_price: '111.23', entry_fees: '0', exit_fees: '0' }, ['0', '$0.00', 'breakeven']],
    [{ average_exit_price: '111.2325', entry_fees: '0', exit_fees: '0' }, ['5000', '$0.01', 'gain']],
    [{ average_exit_price: '111.2275', entry_fees: '0', exit_fees: '0' }, ['-5000', '-$0.01', 'loss']],
    // Rounding gross first would incorrectly turn .005-.01 into zero.
    [{ average_exit_price: '111.2325', entry_fees: '0.01', exit_fees: '0' }, ['-5000', '-$0.01', 'loss']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1', average_exit_price: '111.230001', entry_fees: '0', exit_fees: '0' }, ['1', '<$0.01', 'gain']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1', average_exit_price: '111.229999', entry_fees: '0', exit_fees: '0' }, ['-1', '-<$0.01', 'loss']]
  ];
  for (const [patch, expected] of controls) {
    const env = environment(), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, true, saved.error);
    assert.equal(saved.item.report.exit_fees, '0.00');
    const result = env.handoff.summary(saved.item).completed_result;
    assert.deepEqual([result.net_microusd, result.net_display, result.outcome], expected);
  }
});

test('result arithmetic stays exact beyond safe floating-point integers', async () => {
  const env = environment(), { item } = await env.prepare();
  const saved = await env.handoff.report(item.id, completedFields({ submitted_quantity: '1000000', filled_quantity: '1000000', exited_quantity: '1000000', average_price: '0.000001', average_exit_price: '9999999999.999999', entry_fees: '0.01', exit_fees: '0.02' }), 1);
  assert.equal(saved.ok, true, saved.error);
  const result = env.handoff.summary(saved.item).completed_result;
  assert.equal(result.gross_microusd, '9999999999999998000000');
  assert.equal(result.net_microusd, '9999999999999997970000');
  assert.equal(result.net_display, '$9,999,999,999,999,997.97');
});

test('result fields reject impossible prices and non-cent costs without changing saved facts', async () => {
  const env = environment(), { item } = await env.prepare(), before = env.store.get(env.handoff.KEY);
  for (const patch of [{ average_exit_price: '0' }, { average_exit_price: '-1' }, { average_exit_price: '111.1234567' }, { average_exit_price: '1e3' },
    { entry_fees: '-0.01' }, { entry_fees: '0.001' }, { exit_fees: '90071992547409.92' }, { exit_fees: 0 }, { exited_quantity: '0', exited_at: '' }]) {
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, false, JSON.stringify(patch));
    assert.equal(env.store.get(env.handoff.KEY), before);
  }
});

test('corrections recompute results after expiry and events without restoring entry authority', async () => {
  const env = environment(), { item } = await env.prepare();
  let saved = await env.handoff.report(item.id, completedFields(), 1); assert.equal(saved.ok, true, saved.error);
  env.state.now = '2026-09-12T13:35:00Z'; env.state.restriction = 'Known event exclusion'; env.state.hash = 'b'.repeat(64);
  saved = await env.handoff.report(item.id, { ...saved.item.report, average_exit_price: '109.5' }, saved.item.revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.handoff.summary(saved.item).completed_result.net_display, '-$3.58');
  const revision = saved.item.revision;
  assert.equal((await env.handoff.report(item.id, completedFields(), revision - 1)).ok, false);
  saved = await env.handoff.report(item.id, { ...saved.item.report, exit_fees: '' }, revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.handoff.summary(saved.item).completed_result.state, 'incomplete');
  assert.equal(env.handoff.summary(saved.item).completed_result.net_display, null); assert.equal(env.handoff.copy(item.id).ok, false);
  const reloaded = environment({ store: env.store }); assert.equal(reloaded.handoff.find(item.id).report.exit_fees, null);
});

test('a genuine v1 record reads as unknown new fields without a single storage write', async () => {
  const original = JSON.parse(LEGACY_RAW), old = original.items[0], env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) });
  assert.equal(env.handoff.status().available, true);
  const item = env.handoff.list()[0]; assert.equal(item.version, 2);
  const expected = { ...old, version: 2, report: { ...old.report, average_exit_price: null, entry_fees: null, exit_fees: null } };
  assert.deepEqual(plain(item), expected); assert.equal(env.handoff.find(item.id).revision, old.revision);
  assert.equal(env.handoff.summary(item).completed_result.state, 'incomplete'); assert.equal(env.handoff.summary(item).completed_result.net_display, null);
  assert.equal(env.handoff.copy(item.id).ok, false); assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
  assert.equal(env.handoff.recovery().prior, LEGACY_RAW);
});

test('an explicit valid save upgrades v1 once while preserving original semantics and timestamps', async () => {
  const old = JSON.parse(LEGACY_RAW).items[0], env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) });
  const item = env.handoff.list()[0];
  const bad = await env.handoff.report(item.id, { ...item.report, average_exit_price: 'bad' }, item.revision);
  assert.equal(bad.ok, false); assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
  const saved = await env.handoff.report(item.id, { ...item.report, average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07' }, item.revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.state.writes, 1);
  const raw = env.store.get(env.handoff.KEY), store = JSON.parse(raw); assert.equal(store.version, 2); assert.equal(store.items[0].version, 2);
  assert.equal(saved.item.revision, old.revision + 1); assert.equal(saved.item.created_at, old.created_at);
  for (const key of ['id', 'publication', 'plan', 'draft']) assert.deepEqual(plain(saved.item[key]), old[key]);
  for (const key of Object.keys(old.report)) assert.deepEqual(saved.item.report[key], old.report[key], key);
  assert.equal(env.handoff.summary(saved.item).completed_result.net_display, '$3.65');
  env.handoff.list(); env.handoff.status(); assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 1);
});

test('failed v1 upgrades retain exact old bytes plus proposed v2 recovery and reject stale retries', async () => {
  const env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) }), item = env.handoff.list()[0]; env.state.writeFails = true;
  const fields = { ...item.report, average_exit_price: '115', entry_fees: '0', exit_fees: '0' };
  assert.equal((await env.handoff.report(item.id, fields, item.revision)).ok, false);
  assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.handoff.recovery().prior, LEGACY_RAW);
  const proposed = JSON.parse(env.handoff.recovery().proposed); assert.equal(proposed.version, 2); assert.equal(proposed.items[0].report.entry_fees, '0.00');
  assert.equal(env.handoff.find(item.id).report.entry_fees, null);
  env.state.writeFails = false;
  const saved = await env.handoff.report(item.id, fields, item.revision); assert.equal(saved.ok, true, saved.error);
  assert.equal((await env.handoff.report(item.id, { ...fields, exit_fees: '1' }, item.revision)).ok, false);
  assert.equal(env.handoff.find(item.id).report.exit_fees, '0.00');
});

test('legacy unknown fields and mixed or future versions remain untouched and recoverable', async () => {
  for (const alter of [value => { value.items[0].report.unrecognized = null; }, value => { value.items[0].unexpected = 1; },
    value => { value.items[0].report.entry_fees = '0.00'; }, value => { value.version = 2; }, value => { value.version = 3; }]) {
    const value = JSON.parse(LEGACY_RAW); alter(value); const raw = JSON.stringify(value), env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) });
    assert.equal(env.handoff.status().available, false); assert.equal((await env.prepare()).ok, false);
    assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 0); assert.equal(env.handoff.recovery().prior, raw);
  }
});

test('legacy expansion cannot write past the byte cap or evict another reported position', async () => {
  const source = JSON.parse(LEGACY_RAW).items[0], items = Array.from({ length: 30 }, (_, index) => {
    // Explicit synthetic private-store capacity controls, not public records.
    const item = plain(source); item.publication.sha256 = index.toString(16).padStart(64, '0'); item.id = item.publication.sha256 + ':' + item.plan.reference.id;
    item.plan.exit_schedule = Array.from({ length: 20 }, () => ({ ...item.plan.exit_schedule[0], instruction: 'x' })); return item;
  });
  const cap = environment().handoff.MAX_BYTES, serialize = () => JSON.stringify({ version: 1, items });
  let needed = cap - 8 - Buffer.byteLength(serialize());
  for (const item of items) for (const row of item.plan.exit_schedule) { const add = Math.min(1999, needed); row.instruction += 'x'.repeat(add); needed -= add; }
  assert.equal(needed, 0); const raw = serialize(); assert.equal(Buffer.byteLength(raw), cap - 8);
  const env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) }); assert.equal(env.handoff.status().count, 30); assert.equal(env.state.writes, 0);
  const item = env.handoff.list()[0], saved = await env.handoff.report(item.id, { ...item.report, average_exit_price: '115', entry_fees: '0', exit_fees: '0' }, item.revision);
  assert.equal(saved.ok, false); assert.match(saved.error, /storage is full/);
  assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 0); assert.equal(env.handoff.status().count, 30);
});

test('whole-share exit reference uses personal draft and existing round-up convention without revising the model', async () => {
  for (const [quantity, half, left] of [[1, 1, 0], [2, 1, 1], [3, 2, 1], [4, 2, 2]]) {
    const env = environment(), before = JSON.stringify(env.api.data);
    const result = await env.prepare({ quantity: String(quantity), fees: '0' });
    assert.equal(result.ok, true, result.error);
    const stored = env.store.get(env.handoff.KEY), writes = env.state.writes;
    const review = plain(env.handoff.summary(result.item).exit_review);
    assert.equal(review.basis, 'personal_draft'); assert.equal(review.quantity, quantity);
    assert.equal(review.model_half_quantity, half); assert.equal(review.model_remaining_quantity, left);
    assert.equal(review.needs_review, quantity % 2 !== 0);
    assert.match(review.message, /reference arithmetic/i);
    if (quantity === 1) assert.match(review.message, /one-share position cannot be partly exited/i);
    if (quantity === 3) assert.match(review.message, /rounds up to 2 whole shares/);
    assert.match(env.handoff.readback(result.item), /Whole-share exit reference/);
    assert.equal(result.item.plan.order.quantity, 4);
    assert.equal(JSON.stringify(env.api.data), before); assert.equal(env.store.get(env.handoff.KEY), stored); assert.equal(env.state.writes, writes);
  }
});

test('whole-share exit reference uses reported remaining holdings and never assumes an unknown fill or exit', async () => {
  const env = environment(), { item } = await env.prepare({ quantity: '3' });
  for (const [fields, basis, quantity, half, left] of [
    [{ submitted_quantity: '3' }, 'reported_unknown', null, null, null],
    [{ submitted_quantity: '3', filled_quantity: '3' }, 'reported_unknown', null, null, null],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '0' }, 'reported_remaining', 3, 2, 1],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '1' }, 'reported_remaining', 2, 1, 1],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '2' }, 'reported_remaining', 1, 1, 0],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '3' }, 'reported_remaining', 0, null, null]
  ]) {
    const current = env.handoff.find(item.id);
    const result = await env.handoff.report(item.id, reportFields(fields), current.revision);
    assert.equal(result.ok, true, result.error);
    const review = plain(env.handoff.summary(result.item).exit_review);
    assert.equal(review.basis, basis); assert.equal(review.quantity, quantity);
    assert.equal(review.model_half_quantity, half); assert.equal(review.model_remaining_quantity, left);
    if (quantity === null) assert.match(review.message, /holdings are unknown/i);
    else if (quantity === 0) assert.match(review.message, /reported no remaining shares/i);
    else assert.match(review.message, /does not determine whether another exit is due/i);
    assert.equal(env.handoff.find(item.id).draft.quantity, 3);
  }
});

test('whole-share exit reference reads legacy storage without migration or extra writes', () => {
  const store = new Map([['spicystock:handoff:v1', LEGACY_RAW]]), env = environment({ store });
  const item = env.handoff.list()[0], review = env.handoff.summary(item).exit_review;
  assert.equal(review.basis, 'reported_remaining'); assert.equal(review.quantity, 0);
  assert.equal(review.model_half_quantity, null); assert.equal(review.model_remaining_quantity, null);
  assert.equal(store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
});
