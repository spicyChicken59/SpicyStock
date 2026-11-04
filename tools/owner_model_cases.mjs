/* Owner-trade controls over the real private store (docs/app-handoff.js) in a
   vm, beside tools/handoff_model_cases.mjs: a listed name without a ticket,
   the row frozen as the page reads it, the label and stop validated, the
   sell-half level and the New York fill day, a gap past the reported stop, the
   backup's count and a version 3 store read without a write. Every broker fact
   is synthetic. node --test tools/owner_model_cases.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { createHash } from 'node:crypto';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
// SCSTOCK_HANDOFF routes a copy of the store module, as the page smoke does for a mutant
const scripts = await Promise.all(['docs/app-cash-preview.js', process.env.SCSTOCK_HANDOFF || 'docs/app-handoff.js'].map(f => readFile(path.resolve(ROOT, f), 'utf8')));
const bytes = await readFile(`${ROOT}/tests/fixtures/cash-preview/publication-multiple.json`);
const publication = JSON.parse(bytes.toString('utf8')), sha = createHash('sha256').update(bytes).digest('hex');
function env({ now = '2026-09-11T14:05:00.000Z', fixture = false, hash = sha, store = new Map() } = {}) {
  const data = JSON.parse(bytes.toString('utf8')); if (fixture) data.fixture = 'practice';
  const candidates = data.bursts.map((row, index) => ({ ticker: row.ticker, stage: 'bursts', rank: index + 1, grade: row.grade, score: row.score, admitted: row.admission ? row.admission.admitted : null,
    status: row.plan && row.plan.eligible ? 'ticket' : 'no_order', reason: row.plan && row.plan.eligible ? row.plan.order_line : (row.plan && row.plan.reason) || '', plan: row.plan, row }));
  const NativeDate = Date; const clock = { at: Date.parse(now) };
  const window = { SCStock: { data, model: { stages: { bursts: candidates, 'setting-up': [] } }, observations: { facts: () => ({ canonicalHash: hash }) } }, TextEncoder,
    navigator: { locks: { request: async (k, fn) => fn() } }, localStorage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }, addEventListener: () => {},
    Date: class extends NativeDate { constructor(...args) { super(...(args.length ? args : [clock.at])); } static now() { return clock.at; } } };
  const context = vm.createContext({ window, Date: window.Date }); scripts.forEach(s => vm.runInContext(s, context));
  return { handoff: window.SCStock.handoff, store, clock };
}
const blank = () => Object.fromEntries(['submitted_quantity', 'submitted_at', 'filled_quantity', 'average_price', 'filled_at', 'cancelled_quantity', 'cancelled_at', 'exited_quantity', 'exited_at', 'protected_quantity', 'protection_confirmed_at', 'average_exit_price', 'entry_fees', 'exit_fees', 'account_label', 'stop_price'].map(k => [k, '']));
const filled = patch => ({ ...blank(), submitted_quantity: '102', filled_quantity: '102', average_price: '70.345', filled_at: '2026-09-11T13:41:00Z', account_label: 'Rollover IRA', stop_price: '67.85', ...patch });
const request = { key: 'bursts:NVDA', expectedPublication: sha };
const plain = value => JSON.parse(JSON.stringify(value));

test('an owner trade needs a positive fill and freezes the row, the rules and the calendar sessions', async () => {
  const e = env();
  assert.equal((await e.handoff.reportOwner(request, blank())).ok, false);
  assert.equal((await e.handoff.reportOwner(request, filled({ filled_quantity: '0' }))).ok, false);
  const saved = await e.handoff.reportOwner(request, filled()); assert.equal(saved.ok, true, saved.error);
  assert.equal(saved.item.id, sha + ':owner:bursts:NVDA'); assert.equal(saved.item.version, 4); assert.equal(saved.item.kind, 'owner_trade');
  assert.deepEqual(plain(saved.item.source.row), { rank: 3, grade: 'A+', score: 10, scan: 'both', admitted: true, status: 'no_order', reason: '' });
  assert.deepEqual(plain(saved.item.source.rules), { sell_half_pct: 8, sell_half_day: 3, final_exit_day: 5, entry_day: 1 });
  assert.deepEqual(plain(saved.item.source.schedule), { entry_session: '2026-09-11', sell_half_session: '2026-09-15', final_session: '2026-09-17' });
  assert.equal(saved.item.source.publication.sha256, sha);
  const s = e.handoff.summary(saved.item);
  assert.equal(s.reference_exits.level, '75.97'); assert.equal(s.reference_exits.fill_on_entry_session, true); assert.deepEqual(plain(s.warnings), []);
  assert.equal(s.calculation, null); assert.equal(e.handoff.readback(saved.item), ''); assert.equal(e.handoff.copy(saved.item.id).ok, false);
});
test('a second record for the same name in the same record is refused and names the existing one', async () => {
  const e = env(); const first = await e.handoff.reportOwner(request, filled());
  const again = await e.handoff.reportOwner(request, filled()); assert.equal(again.ok, false); assert.equal(again.existingId, first.item.id);
  assert.equal(e.handoff.list().length, 1);
});
test('a ticketed name, a practice record, another publication and an unlisted name are refused by name', async () => {
  assert.match((await env().handoff.reportOwner({ key: 'bursts:AAPL', expectedPublication: sha }, filled())).error, /published ticket/);
  assert.match((await env({ fixture: true }).handoff.reportOwner(request, filled())).error, /practice record/);
  assert.match((await env().handoff.reportOwner({ key: 'bursts:NVDA', expectedPublication: '0'.repeat(64) }, filled())).error, /another or unverified publication/);
  assert.match((await env().handoff.reportOwner({ key: 'bursts:ZZZZ', expectedPublication: sha }, filled())).error, /not in the current record/);
  assert.match((await env().handoff.reportOwner({ key: 'setting-up:NVDA', expectedPublication: sha }, filled())).error, /not in the current record/);
});
test('the label and the stop are validated as the page says', async () => {
  const e = env();
  assert.match((await e.handoff.reportOwner(request, filled({ account_label: 'R'.repeat(41) }))).error, /at most 40/);
  assert.match((await e.handoff.reportOwner(request, filled({ account_label: 'Roth\u0007IRA' }))).error, /at most 40/);
  assert.match((await e.handoff.reportOwner(request, filled({ stop_price: '0' }))).error, /protective stop price must be positive/);
  assert.match((await e.handoff.reportOwner(request, filled({ stop_price: '67.8500001' }))).error, /protective stop price must be positive/);
  const saved = await e.handoff.reportOwner(request, filled({ account_label: '  Roth IRA  ', stop_price: '' }));
  assert.equal(saved.ok, true, saved.error); assert.equal(saved.item.report.account_label, 'Roth IRA'); assert.equal(saved.item.report.stop_price, null);
  assert.equal(e.handoff.summary(saved.item).beyond_stop, null);
});
test('the sell-half level rounds to the cent half up and the fill day is the New York date', async () => {
  const e = env({ now: '2026-09-14T20:00:00.000Z' }); const saved = await e.handoff.reportOwner(request, filled({ average_price: '61.72', filled_at: '2026-09-12T03:30:00Z' }));
  assert.equal(saved.ok, true, saved.error);
  const r = e.handoff.summary(saved.item).reference_exits;
  assert.equal(r.level, '66.66'); assert.equal(r.fill_session, '2026-09-11'); assert.equal(r.fill_on_entry_session, true);
  const corrected = await e.handoff.report(saved.item.id, { ...saved.item.report, filled_at: '2026-09-14T13:41:00.000Z' }, saved.item.revision);
  assert.equal(corrected.ok, true, corrected.error);
  const s = e.handoff.summary(corrected.item);
  assert.equal(s.reference_exits.fill_on_entry_session, false); assert.equal(s.warnings.length, 1); assert.match(s.warnings[0], /2026-09-14 \(New York\) is not the session/);
});
test('a gap past the reported stop is measured against it', async () => {
  const e = env(); const saved = await e.handoff.reportOwner(request, filled({ cancelled_quantity: '0' }));
  e.clock.at = Date.parse('2026-09-14T20:00:00Z');
  const exited = await e.handoff.report(saved.item.id, { ...saved.item.report, exited_quantity: 102, exited_at: '2026-09-14T14:35:00.000Z', average_exit_price: '67.1', entry_fees: '0.00', exit_fees: '0.01' }, saved.item.revision);
  assert.equal(exited.ok, true, exited.error);
  const s = e.handoff.summary(exited.item);
  assert.equal(s.completed_result.net_display, '-$331.00'); assert.equal(s.beyond_stop.total_display, '$76.50'); assert.equal(s.beyond_stop.per_share_display, '$0.75');
});
test('the backup counts owner trades apart and a version 3 store reads without a write', async () => {
  const e = env(); await e.handoff.reportOwner(request, filled());
  const backup = e.handoff.exportBackup(); assert.equal(backup.summary.owner_count, 1); assert.equal(backup.summary.version, 4);
  // a version 3 store holding the first-trade rehearsal's two planned records
  const v3 = JSON.parse(await readFile(path.resolve(ROOT, 'tests/fixtures/first-trade/backup.json'), 'utf8')); v3.version = 3;
  for (const item of v3.items) { item.version = 3; delete item.report.account_label; delete item.report.stop_price; }
  const seeded = env({ store: new Map([['spicystock:handoff:v1', JSON.stringify(v3)]]) });
  assert.equal(seeded.handoff.status().available, true); assert.equal(seeded.store.get('spicystock:handoff:v1'), JSON.stringify(v3));
  assert.deepEqual(plain(seeded.handoff.list().map(i => [i.version, i.kind, i.report.account_label, i.report.stop_price])), [[4, 'planned_handoff', null, null], [4, 'planned_handoff', null, null]]);
  const owner3 = JSON.parse(backup.raw); owner3.version = 3; for (const item of owner3.items) { item.version = 3; delete item.report.account_label; delete item.report.stop_price; }
  assert.equal(env({ store: new Map([['spicystock:handoff:v1', JSON.stringify(owner3)]]) }).handoff.status().available, false, 'an owner trade under a version 3 envelope is refused');
});
