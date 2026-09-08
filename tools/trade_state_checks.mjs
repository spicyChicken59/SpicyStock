import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const engine = require('../docs/trade-state.js');
const NOW = Date.parse('2026-09-08T15:00:00Z');
const KEY = 'spicystock.trades.v2';
const LEGACY_KEY = 'spicystock.trade-journal.v1';
let passed = 0;

function memory(seed = {}) {
  const values = new Map(Object.entries(seed));
  return { values, getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}
function store(storage = memory()) { return engine.createStore({ storage, clock: () => NOW, listen: false }); }
function check(name, fn) {
  try { fn(); passed++; console.log(`PASS ${name}`); }
  catch (error) { console.error(`FAIL ${name}`); throw error; }
}
function ok(result) { assert.equal(result.ok, true, result.error || result.errors?.join('; ')); return result; }
function bad(result, pattern) {
  assert.equal(result.ok, false);
  if (pattern) assert.match(result.error || result.errors?.join('; ') || '', pattern);
  return result;
}
function fill(id, values = {}) {
  return { execution_id: id, symbol: 'BEE', side: 'buy', qty: 10, price: 100,
    executed_at: '2026-09-08T13:30:00Z', fees: 0, initial_stop: 95,
    source: 'manual', environment: 'live', account_id: 'local', confirmed: true, ...values };
}
function plan(values = {}) {
  return { symbol: 'BEE', snapshot_date: '2026-09-04', capital: 10000,
    risk_percent: 1, cash_cap: 10000, entry: 100, stop: 95, status: 'prepared', ...values };
}
function csvCell(value) {
  const s = value === null || value === undefined ? '' : String(value);
  return /[",\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}
function csv(rows) {
  return engine.csvColumns.join(',') + '\r\n' + rows.map(row => engine.csvColumns.map(key => csvCell(row[key])).join(',')).join('\r\n') + '\r\n';
}
function imported(s, rows) { return ok(s.commitImport(ok(s.previewImport(csv(rows), 'csv')))); }
function brokerFill(id, values = {}) {
  return { id, symbol: 'BEE', side: 'buy', qty: 10, price: 100,
    transaction_time: '2026-09-08T13:30:00Z', fees: 0,
    source: 'alpaca', mode: 'paper', account_id: 'broker-one', order_id: 'order-one', ...values };
}
function portfolio(values = {}) {
  return { mode: 'paper', account: { id: 'broker-one', cash: 9000, equity: 10000, buying_power: 9000 },
    as_of: '2026-09-08T14:30:00Z', fills: [], positions: [], unresolved: [], ...values };
}

check('whole shares respect risk and cash; invalid inputs cannot size a trade', () => {
  assert.equal(ok(engine.calculate(plan())).qty, 20);
  const capped = ok(engine.calculate(plan({ cash_cap: 999 })));
  assert.equal(capped.qty, 9);
  assert.equal(capped.planned_risk, 45);
  assert.equal(capped.position_cost, 900);
  assert.equal(ok(engine.calculate(plan({ risk_percent: 0 }))).qty, 0);
  // Decimal currency arithmetic must not lose a whole share to a float rounding tail.
  const decimalEntry = 10.6, decimalStop = decimalEntry - 0.37, decimalCapital = decimalEntry * 13;
  assert.equal(ok(engine.calculate(plan({ capital: decimalCapital, cash_cap: decimalCapital, entry: decimalEntry, stop: decimalStop, risk_percent: (decimalEntry - decimalStop) / decimalEntry * 100 }))).qty, 13);
  assert.equal(ok(engine.calculate(plan({ capital: 137.79, cash_cap: 137.79, entry: 10.6, stop: 10.23, risk_percent: 100 }))).qty, 12);
  for (const patch of [{ stop: 100 }, { stop: 0 }, { capital: -1 }, { cash_cap: 10001 }, { risk_percent: Infinity }, { risk_percent: '' }, { max_positions: 1.5 }]) bad(engine.calculate(plan(patch)));
});

check('plans and submissions are never executions; submitted terms stay frozen', () => {
  const s = store();
  const saved = ok(s.savePlan(plan())).plan;
  assert.equal(s.derive().positions.length, 0);
  bad(s.savePlan({ ...saved, status: 'submitted', order_id: 'order-one' }), /identifiers/);
  const submitted = ok(s.savePlan({ ...saved, status: 'submitted', order_id: 'order-one', account_id: 'broker-one', environment: 'paper' })).plan;
  bad(s.savePlan({ ...submitted, entry: 99 }), /frozen/);
  bad(s.savePlan({ ...submitted, status: 'draft' }), /frozen/);
  const canceled = ok(s.savePlan({ ...submitted, status: 'canceled' })).plan;
  bad(s.savePlan({ ...canceled, status: 'prepared' }), /cannot be reopened/);
  assert.equal(s.getState().fills.length, 0);
  bad(s.savePlan(plan({ risk_percent: 0 })), /one share/);
});

check('manual executions require confirmation and cannot impersonate broker sync', () => {
  const s = store();
  bad(s.recordFill(fill('missing-confirmation', { confirmed: false })), /Confirm/);
  bad(s.recordFill(fill('pretend-broker', { source: 'alpaca' })), /Broker executions/);
  assert.equal(s.getState().fills.length, 0);
  ok(s.recordFill(fill('actual-fill')));
  assert.equal(s.derive().positions[0].qty, 10);
});

check('FIFO partial exits allocate both execution fees and original risk correctly', () => {
  const s = store();
  ok(s.recordFill(fill('buy-one', { fees: 1 })));
  ok(s.recordFill(fill('buy-two', { price: 110, initial_stop: 100, fees: 2, executed_at: '2026-09-08T13:35:00Z' })));
  ok(s.recordFill(fill('exit', { side: 'sell', qty: 15, price: 120, fees: 3, executed_at: '2026-09-08T14:00:00Z' })));
  const d = s.derive();
  assert.equal(d.closed.length, 2);
  assert.deepEqual(d.closed.map(r => [r.qty, r.profit, r.fees, r.net_profit, r.initial_risk, r.r, r.net_r]), [[10, 200, 3, 197, 50, 4, 3.94], [5, 50, 2, 48, 50, 1, 0.96]]);
  assert.equal(d.positions[0].qty, 5);
  assert.equal(d.positions[0].average_entry, 110);
  assert.equal(d.positions[0].initial_risk, 50);
  assert.equal(d.totals.live.realized_gross, 250);
  assert.equal(d.totals.live.realized_net, 245);
});

check('unknown fees or initial stop remain unknown without invented net return or R', () => {
  const s = store();
  ok(s.recordFill(fill('buy', { fees: null, initial_stop: null })));
  assert.equal(s.derive().totals.live.initial_risk, null);
  ok(s.recordFill(fill('sell', { side: 'sell', price: 110, executed_at: '2026-09-08T14:00:00Z' })));
  const d = s.derive();
  assert.equal(d.closed[0].profit, 100);
  for (const key of ['fees', 'net_profit', 'initial_risk', 'r', 'net_r']) assert.equal(d.closed[0][key], null);
  assert.equal(d.totals.live.realized_net, null);
});

check('actual execution chronology controls matching, independent of CSV row order', () => {
  const s = store();
  imported(s, [fill('sell', { side: 'sell', price: 110, executed_at: '2026-09-08T10:00:00-04:00' }), fill('buy')]);
  assert.equal(s.derive().closed[0].profit, 100);
  assert.equal(s.derive().reconciliation.length, 0);
  assert.equal(s.getState().fills[0].executed_at, '2026-09-08T14:00:00.000Z');
});

check('manual oversells and sells preceding a buy fail atomically', () => {
  const s = store();
  bad(s.recordFill(fill('first-sell', { side: 'sell' })), /exceeds recorded earlier buys/);
  ok(s.recordFill(fill('buy')));
  const before = s.exportJSON();
  bad(s.recordFill(fill('too-early', { side: 'sell', executed_at: '2026-09-08T13:00:00Z' })), /exceeds recorded earlier buys/);
  bad(s.recordFill(fill('too-large', { side: 'sell', qty: 11, executed_at: '2026-09-08T14:00:00Z' })), /exceeds recorded earlier buys/);
  assert.equal(s.exportJSON(), before);
});

check('imported missing history is retained for reconciliation and suppresses performance', () => {
  const s = store();
  const preview = ok(s.previewImport(csv([fill('buy'), fill('oversell', { side: 'sell', qty: 12, price: 110, executed_at: '2026-09-08T14:00:00Z' })]), 'csv'));
  assert.ok(preview.warnings.some(w => /Reconciliation required/.test(w)));
  ok(s.commitImport(preview));
  const d = s.derive();
  assert.equal(d.reconciliation[0].qty, 2);
  assert.equal(d.closed[0].reconciled, false);
  assert.equal(d.closed[0].profit, null);
  assert.equal(d.closed[0].r, null);
  assert.equal(d.totals.live.realized_gross, null);
  assert.equal(d.totals.live.realized_net, null);
});

check('source, environment and account keep matching and execution identity separate', () => {
  const s = store();
  const rows = [fill('same-id'), fill('same-id', { environment: 'paper' }), fill('same-id', { account_id: 'second' }), fill('same-id', { source: 'alpaca', executed_at: '2026-09-08T13:32:00Z' })];
  imported(s, rows);
  assert.equal(s.getState().fills.length, 4);
  assert.equal(s.derive().positions.length, 4);
  ok(s.recordFill(fill('exit', { side: 'sell', environment: 'paper', price: 110, executed_at: '2026-09-08T14:00:00Z' })));
  assert.equal(s.derive().positions.length, 3);
  assert.equal(s.derive().totals.paper.realized_gross, 100);
  assert.equal(s.derive().totals.live.realized_gross, 0);
});

check('quoted CSV fields, escaped quotes, CRLF and BOM round-trip without data loss', () => {
  const s = store();
  const row = fill('exec,"one"', { account_id: 'my, "account"' });
  const preview = ok(s.previewImport('\uFEFF' + csv([row]), 'csv'));
  assert.equal(preview.rows[0].execution_id, 'exec,"one"');
  assert.equal(preview.rows[0].account_id, 'my, "account"');
  assert.equal(s.getState().fills.length, 0);
  ok(s.commitImport(preview));
  const other = store();
  ok(other.commitImport(ok(other.previewImport(s.exportCSV(), 'csv'))));
  assert.deepEqual(other.getState().fills, s.getState().fills);
});

check('malformed CSV and any invalid row reject the entire import', () => {
  const s = store();
  const before = s.exportJSON();
  for (const input of [csv([fill('good'), fill('bad', { qty: -1 })]), csv([fill('good')]).replace('execution_id', 'id'), engine.csvColumns.join(',') + '\n"unterminated', engine.csvColumns.join(',') + '\n"a"x,b', engine.csvColumns.join(',') + '\nx"a,b', engine.csvColumns.join(',') + '\nonly,two']) {
    bad(s.previewImport(input, 'csv'));
    assert.equal(s.exportJSON(), before);
  }
});

check('repeated executions deduplicate; conflicting IDs stop even an otherwise valid batch', () => {
  const s = store();
  const first = imported(s, [fill('same'), fill('same')]);
  assert.equal(first.added, 1);
  assert.equal(first.duplicates, 1);
  assert.equal(imported(s, [fill('same')]).added, 0);
  const before = s.exportJSON();
  bad(s.previewImport(csv([fill('new'), fill('same', { qty: 20 })]), 'csv'), /collision/);
  bad(s.previewImport(csv([fill('another'), fill('another', { qty: 20 })]), 'csv'), /collision/);
  assert.equal(s.exportJSON(), before);
});

check('preview confirmation is bound to reviewed content and the current revision', () => {
  const s = store();
  const changed = ok(s.previewImport(csv([fill('one')]), 'csv'));
  changed.rows[0].qty = 99;
  bad(s.commitImport(changed), /expired or changed/);
  const stale = ok(s.previewImport(csv([fill('two')]), 'csv'));
  ok(s.setProfile({ capital: 10000, risk_percent: 1 }));
  bad(s.commitImport(stale), /expired or changed/);
  const fresh = ok(s.previewImport(csv([fill('three')]), 'csv'));
  ok(s.commitImport(fresh));
  bad(s.commitImport(fresh), /expired or changed/);
  assert.equal(s.getState().fills.length, 1);
});

check('JSON backups restore fills, plans and corrections while preserving current profile', () => {
  const source = store();
  ok(source.setProfile({ capital: 50000, risk_percent: 2 }));
  ok(source.savePlan(plan()));
  const entry = ok(source.recordFill(fill('corrected'))).fill;
  ok(source.voidFill(entry.id, { confirmed: true, reason: 'Mistyped the fill' }));
  ok(source.recordFill(fill('correct')));
  const target = store();
  ok(target.setProfile({ capital: 12345, risk_percent: 0.5 }));
  const expectedProfile = target.getState().profile;
  ok(target.commitImport(ok(target.previewImport(source.exportJSON(), 'json'))));
  assert.deepEqual(target.getState().profile, expectedProfile);
  assert.deepEqual(target.getState().fills, source.getState().fills);
  assert.deepEqual(target.getState().plans, source.getState().plans);
  assert.deepEqual(target.getState().voids, source.getState().voids);
  assert.equal(target.derive().positions[0].qty, 10);
  const emptyTarget = store();
  ok(emptyTarget.commitImport(ok(emptyTarget.previewImport(source.exportJSON(), 'json'))));
  assert.equal(emptyTarget.getState().profile.capital, null);
});

check('JSON plan collisions and malformed identities cannot partially restore a backup', () => {
  const s = store();
  ok(s.savePlan(plan({ id: 'shared-plan' })));
  const conflicting = JSON.parse(s.exportJSON());
  conflicting.plans[0].entry = 99;
  const before = s.exportJSON();
  bad(s.previewImport(JSON.stringify(conflicting), 'json'), /collision/);
  const source = store(); ok(source.recordFill(fill('one')));
  const malformed = JSON.parse(source.exportJSON()); malformed.fills[0].id = 'forged';
  bad(s.previewImport(JSON.stringify(malformed), 'json'), /identity/);
  assert.equal(s.exportJSON(), before);
});

check('legacy open and closed journals migrate as reviewed drafts without fabricated fills', () => {
  const raw = JSON.stringify({ version: 1, records: ['paper', 'open', 'closed'].map((status, i) => ({ id: `old-${i}`, ticker: 'BEE', status, date: '2026-09-04', entry: 100, stop: 95, shares: 10, exit: 120, exitDate: '2026-09-08' })) });
  const storage = memory({ [LEGACY_KEY]: raw }); const s = store(storage);
  const preview = ok(s.previewLegacy());
  assert.equal(s.getState().plans.length, 0);
  assert.ok(preview.warnings.some(w => /draft plans only/.test(w)));
  ok(s.commitImport(preview));
  assert.equal(s.getState().plans.length, 3);
  assert.ok(s.getState().plans.every(p => p.status === 'draft'));
  assert.equal(s.getState().fills.length, 0);
  assert.equal(s.derive().closed.length, 0);
  assert.equal(storage.getItem(LEGACY_KEY), raw);
});

check('corrupt and blocked storage preserve the stored copy and keep temporary changes usable', () => {
  const corrupt = memory({ [KEY]: '{not-json' }); const s = store(corrupt);
  assert.equal(s.load().fills.length, 0);
  assert.equal(s.getStorageStatus().temporary, true);
  assert.equal(ok(s.recordFill(fill('one'))).temporary, true);
  assert.equal(corrupt.getItem(KEY), '{not-json');
  assert.equal(JSON.parse(s.exportJSON()).fills.length, 1);
  const blocked = store({ getItem() { throw Error('denied'); }, setItem() { throw Error('denied'); } });
  assert.equal(ok(blocked.savePlan(plan())).temporary, true);
  assert.match(blocked.getStorageStatus().reason, /Temporary mode/);
});

check('quota and cross-tab writes preserve the newer durable ledger without losing this visit', () => {
  const storage = memory(); const first = store(storage);
  ok(first.recordFill(fill('first')));
  const durable = storage.getItem(KEY);
  storage.setItem = () => { throw Error('quota'); };
  assert.equal(ok(first.recordFill(fill('second'))).temporary, true);
  assert.equal(storage.getItem(KEY), durable);
  assert.equal(first.getState().fills.length, 2);
  const shared = memory(); const a = store(shared); const b = store(shared);
  a.load(); b.load();
  ok(a.recordFill(fill('tab-a')));
  const newer = shared.getItem(KEY);
  assert.equal(ok(b.recordFill(fill('tab-b'))).temporary, true);
  assert.equal(shared.getItem(KEY), newer);
  assert.deepEqual(b.getState().fills.map(f => f.execution_id), ['tab-b']);
  assert.deepEqual(store(shared).getState().fills.map(f => f.execution_id), ['tab-a']);
});

check('broker pending orders and reported holdings never manufacture executions', () => {
  const s = store();
  ok(s.ingestBroker(portfolio({ orders: [{ id: 'pending', symbol: 'BEE', side: 'buy', qty: 10, status: 'new', filled_qty: 0 }], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100, current_price: 105, market_value: 1050 }] })));
  assert.equal(s.getState().fills.length, 0);
  assert.equal(s.derive().positions.length, 0);
  assert.equal(s.derive().broker_positions[0].qty, 10);
  assert.equal(s.derive().totals.paper.reconciliation_required, true);
  assert.equal(s.derive().totals.paper.realized_gross, null);
});

check('a manually entered copy of a synced execution is rejected without double counting', () => {
  const s = store();
  ok(s.ingestBroker(portfolio({ fills: [brokerFill('broker-fill')], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100 }] })));
  const before = s.exportJSON();
  bad(s.recordFill(fill('manual-copy', { environment: 'paper', executed_at: '2026-09-08T13:30:30Z' })), /already synced/);
  assert.equal(s.exportJSON(), before);
  assert.equal(s.derive().positions[0].qty, 10);
});

check('later broker sync flags a probable manual duplicate and withholds exposure until corrected', () => {
  const s = store();
  const manual = ok(s.recordFill(fill('manual-first', { environment: 'paper' }))).fill;
  ok(s.ingestBroker(portfolio({ fills: [brokerFill('broker-fill')], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100 }] })));
  const d = s.derive();
  assert.equal(s.getState().fills.length, 2);
  assert.ok(d.reconciliation.some(r => /manual execution resembles/.test(r.reason)));
  assert.equal(d.totals.paper.open_cost, null);
  assert.equal(d.totals.paper.initial_risk, null);
  assert.equal(d.totals.paper.realized_gross, null);
  ok(s.voidFill(manual.id, { confirmed: true, reason: 'This manually recorded fill is now imported from the broker.' }));
  assert.equal(s.derive().reconciliation.length, 0);
  assert.equal(s.derive().totals.paper.open_cost, 1000);
  assert.equal(s.derive().positions.length, 1);
});

check('broker source, account and environment mismatch reject sync atomically', () => {
  const s = store();
  for (const patch of [{ account_id: 'wrong' }, { mode: 'live' }, { source: 'manual' }]) {
    const before = s.exportJSON();
    bad(s.ingestBroker(portfolio({ fills: [brokerFill('valid'), brokerFill('bad', patch)] })), /does not match/);
    assert.equal(s.exportJSON(), before);
  }
});

check('partial broker executions sync once and conflicting execution values are rejected', () => {
  const s = store();
  const positions = [{ symbol: 'BEE', qty: 10, avg_entry_price: 100, current_price: 101, market_value: 1010 }];
  const p = portfolio({ fills: [brokerFill('part-one', { qty: 4 }), brokerFill('part-two', { qty: 6 })], positions });
  assert.equal(ok(s.ingestBroker(p)).added, 2);
  assert.equal(s.derive().positions[0].qty, 10);
  assert.equal(s.derive().reconciliation.length, 0);
  const again = ok(s.ingestBroker(p));
  assert.equal(again.added, 0); assert.equal(again.duplicates, 2);
  const before = s.exportJSON();
  bad(s.ingestBroker({ ...p, fills: [brokerFill('part-one', { qty: 5 })] }), /collision/);
  bad(s.ingestBroker({ ...p, as_of: '2026-09-08T14:00:00Z' }), /older/);
  assert.equal(s.exportJSON(), before);
});

check('broker CSV export preserves execution and order identity through repeated sync', () => {
  const source = store();
  const p = portfolio({ fills: [brokerFill('one')], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100 }] });
  ok(source.ingestBroker(p));
  const target = store();
  ok(target.commitImport(ok(target.previewImport(source.exportCSV(), 'csv'))));
  assert.deepEqual(target.getState().fills, source.getState().fills);
  assert.equal(target.getState().fills[0].order_id, 'order-one');
  const synced = ok(target.ingestBroker(p));
  assert.equal(synced.added, 0);
  assert.equal(synced.duplicates, 1);
});

check('backup restore preserves incomplete-history warnings on an otherwise empty ledger', () => {
  const source = store();
  const fills = [brokerFill('buy'), brokerFill('sell', { side: 'sell', price: 110, transaction_time: '2026-09-08T14:00:00Z' })];
  ok(source.ingestBroker(portfolio({ fills, fills_truncated: true })));
  const target = store();
  ok(target.commitImport(ok(target.previewImport(source.exportJSON(), 'json'))));
  assert.deepEqual(target.getState().broker_snapshots, source.getState().broker_snapshots);
  assert.equal(target.derive().totals.paper.reconciliation_required, true);
  assert.equal(target.derive().totals.paper.realized_gross, null);
  assert.equal(target.derive().closed[0].r, null);
});

check('confirmed links retain original plan risk without changing broker execution records', () => {
  const s = store();
  const p = ok(s.savePlan(plan({ environment: 'paper', account_id: 'broker-one' }))).plan;
  ok(s.ingestBroker(portfolio({ fills: [brokerFill('one')], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100 }] })));
  const f = s.getState().fills[0];
  assert.equal(s.derive().positions[0].initial_risk, null);
  bad(s.linkFillToPlan(f.id, p.id, { confirmed: false }), /Confirm/);
  const wrong = ok(s.savePlan(plan({ environment: 'live', account_id: 'broker-one' }))).plan;
  bad(s.linkFillToPlan(f.id, wrong.id, { confirmed: true }), /cannot be linked/);
  ok(s.linkFillToPlan(f.id, p.id, { confirmed: true }));
  assert.equal(s.derive().positions[0].initial_risk, 50);
  assert.deepEqual(s.getState().fills[0], f);
  bad(s.linkFillToPlan(f.id, p.id, { confirmed: true }), /cannot be linked/);
  bad(s.savePlan({ ...p, stop: 96 }), /frozen/);
  const restored = store();
  ok(restored.commitImport(ok(restored.previewImport(s.exportJSON(), 'json'))));
  assert.deepEqual(restored.getState().links, s.getState().links);
  assert.equal(restored.derive().positions[0].initial_risk, 50);
});

check('automatic plan linkage requires matching broker order, symbol, environment and account', () => {
  const s = store();
  ok(s.savePlan(plan({ order_id: 'order-one', environment: 'live', account_id: 'broker-one' })));
  ok(s.savePlan(plan({ order_id: 'order-one', environment: 'paper', account_id: 'other-account' })));
  const p = portfolio({ fills: [brokerFill('one')], positions: [{ symbol: 'BEE', qty: 10, avg_entry_price: 100 }] });
  ok(s.ingestBroker(p));
  assert.equal(s.getState().links.length, 0);
  const right = ok(s.savePlan(plan({ order_id: 'order-one', environment: 'paper', account_id: 'broker-one' }))).plan;
  ok(s.ingestBroker(p));
  assert.equal(s.getState().links.length, 1);
  assert.equal(s.getState().links[0].plan_id, right.id);
  assert.equal(s.derive().positions[0].initial_risk, 50);
});

check('incomplete broker history withholds results until a complete matching observation arrives', () => {
  const s = store();
  const fills = [brokerFill('buy'), brokerFill('sell', { side: 'sell', price: 110, transaction_time: '2026-09-08T14:00:00Z' })];
  ok(s.ingestBroker(portfolio({ fills, fills_truncated: true })));
  assert.equal(s.derive().closed[0].profit, null);
  assert.equal(s.derive().totals.paper.realized_net, null);
  ok(s.ingestBroker(portfolio({ fills, as_of: '2026-09-08T14:35:00Z' })));
  assert.equal(s.derive().closed[0].profit, 100);
  assert.equal(s.derive().totals.paper.realized_net, 100);
  const backedUp = s.exportJSON(); const other = store();
  ok(other.ingestBroker(portfolio({ as_of: '2026-09-08T14:40:00Z', positions: [{ symbol: 'BEE', qty: 5, avg_entry_price: 100 }] })));
  ok(other.commitImport(ok(other.previewImport(backedUp, 'json'))));
  assert.equal(other.getState().broker_snapshots[0].as_of, '2026-09-08T14:40:00.000Z');
  assert.equal(other.derive().totals.paper.realized_gross, null);
});

check('corrections preserve audit records, need confirmation and cannot void broker executions', () => {
  const s = store(); const manual = ok(s.recordFill(fill('manual'))).fill;
  bad(s.voidFill(manual.id, { confirmed: false, reason: 'Wrong entry' }), /Confirm/);
  bad(s.voidFill(manual.id, { confirmed: true, reason: '' }), /Confirm/);
  ok(s.voidFill(manual.id, { confirmed: true, reason: 'Wrong entry' }));
  assert.equal(s.getState().fills.length, 1);
  assert.equal(s.getState().voids.length, 1);
  assert.equal(s.derive().positions.length, 0);
  assert.equal(s.parseCSV(s.exportCSV()).length, 1);
  bad(s.voidFill(manual.id, { confirmed: true, reason: 'Again' }), /already/);
  imported(s, [fill('broker', { source: 'alpaca' })]);
  const broker = s.getState().fills.find(f => f.source === 'alpaca');
  bad(s.voidFill(broker.id, { confirmed: true, reason: 'Wrong' }), /Only a manually recorded/);
});

check('public snapshots and subscriber callbacks cannot mutate the ledger', () => {
  const s = store(); let notifications = 0;
  const unsubscribe = s.subscribe(state => { notifications++; state.fills.length = 0; });
  ok(s.recordFill(fill('first')));
  const snapshot = s.getState(); snapshot.fills[0].qty = 999;
  assert.equal(s.getState().fills[0].qty, 10);
  assert.equal(notifications, 1);
  unsubscribe(); ok(s.recordFill(fill('second')));
  assert.equal(notifications, 1);
  assert.equal(s.getState().fills.length, 2);
});

check('invalid calendar dates, timezone-free and future times cannot become completed fills', () => {
  const s = store();
  for (const executed_at of ['2026-02-30T13:00:00Z', '2026-09-08T13:00:00', '2026-09-08T24:00:00Z', '2026-09-09T13:00:00Z']) bad(s.recordFill(fill(executed_at, { executed_at })), /Execution time/);
  assert.equal(s.getState().fills.length, 0);
  bad(s.recordFill(fill('pipe-id', { account_id: 'account|other' })), /valid account/);
});

console.log(`Trade-state checks passed: ${passed} groups.`);
